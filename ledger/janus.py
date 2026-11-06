"""Janus: an AI discretionary paper book (an experiment in AI judgement; no edge is claimed).

    python -m ledger.janus run [--dry-run]     # weekly review + new positions (Anthropic API, web search)
    python -m ledger.janus mark [--today D]    # daily: fill pending entries, close on stop/horizon/close request
    python -m ledger.janus verify              # check the hash chain (exit 1 on failure)
    python -m ledger.janus status              # print the book

Account: separate paper account of US$500,000,000, reported in % (index 100 at its start). Its results never feed
the algorithm (v1.0/v1.1) and the algorithm never reads data/janus/.

Records (data/janus/records.jsonl) are append-only and hash-chained: each line carries ``seq``, ``prev_hash`` and
``hash`` = SHA-256 of the previous hash and the canonical JSON of the record without ``hash``. Nothing is edited:
a fill, a stop change, a close or a review is a new record. ``verify`` re-computes the chain.

Rules (enforced in code, not left to the model):
  * universe: only instruments with a free public daily mark (``UNIVERSE``; dropped markets in ``DROPPED``);
  * size = % of account at risk to the stop; at most 2% per position, 10% in total, 8 open positions;
  * capacity (ledger/capacity.py): notional at most 10% of the instrument's ADV and below 80% of any exchange
    position limit, else the size is cut to fit (logged);
  * entry at the next available daily mark: the first first-hand daily mark dated on or after the decision's UTC
    date (a mark dated before the decision cannot be traded on); if that mark is already through the stop the
    order is cancelled;
  * stops can only be tightened; positions close automatically at the first daily mark through the stop, at the
    first mark dated on or after the horizon, or at the first mark dated on or after a close decision;
  * costs: the algorithm's cost model (10bp of notional per one-way trade for major FX and developed bonds, 20bp
    for a spread, two legs) and, for commodity futures, the T20-T22 model (2 x (US$3 commission + 1 tick) per
    contract per side, a roll counted as two trades), plus the square-root impact estimate on every trade;
  * commodity roll rule (logged with each fill and roll): hold the earliest contract whose notice date is more
    than 35 calendar days after the trade date (T20-T22's buffer); roll when the held contract is within 10
    calendar days of its notice date. Notice dates are calendar approximations (``NOTICE_RULES``). Because no free
    futures settlement exists, commodity P&L is marked on the official spot price (an estimate; roll yield is not
    captured, roll costs are charged).
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import capacity as CAP
from . import pricing as PX
from .marks import load_registry, mark_can_act, read_marks
from .schema import parse_date

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data/janus"
RECORDS = DIR / "records.jsonl"
ACCOUNT_USD = CAP.JANUS_CAPITAL
MAX_RISK_POS, MAX_RISK_TOTAL, MAX_OPEN = 2.0, 10.0, 8
MIN_HORIZON_DAYS, MAX_HORIZON_DAYS = 5, 190
ROLL_BUFFER_DAYS, ROLL_BEFORE_NOTICE_DAYS = 35, 10
MONTH_CODES = "FGHJKMNQUVXZ"
GENESIS = "0" * 64

# instrument -> description; ``cost`` is the one-way cost per unit of notional (the algorithm's model)
UNIVERSE = {
    "WTI": dict(name="WTI crude oil, NYMEX CL front month", asset_class="commodity", sector="energy", country="United States",
                currency="USD", contract="CL", exchange="NYMEX", multiplier=1000, tick_value=10.0, estimate=True),
    "BRENT": dict(name="Brent crude oil, ICE B front month", asset_class="commodity", sector="energy", country="Global",
                  currency="USD", contract="B", exchange="ICE Futures Europe", multiplier=1000, tick_value=10.0, estimate=True),
    "NATGAS": dict(name="Henry Hub natural gas, NYMEX NG front month", asset_class="commodity", sector="energy",
                   country="United States", currency="USD", contract="NG", exchange="NYMEX", multiplier=10000,
                   tick_value=10.0, estimate=True),
    "HEATOIL": dict(name="NY Harbor ULSD / heating oil, NYMEX HO front month", asset_class="commodity", sector="energy",
                    country="United States", currency="USD", contract="HO", exchange="NYMEX", multiplier=42000,
                    tick_value=4.2, estimate=True),
    "RBOB": dict(name="RBOB gasoline, NYMEX RB front month", asset_class="commodity", sector="energy", country="United States",
                 currency="USD", contract="RB", exchange="NYMEX", multiplier=42000, tick_value=4.2, estimate=True),
    "US10Y": dict(name="US 10-year Treasury (long = long the bond)", asset_class="rates", country="United States",
                  currency="USD", cost=0.001),
    "DE10Y": dict(name="German 10-year Bund (long = long the bond)", asset_class="rates", country="Germany", currency="EUR",
                  cost=0.001),
    "GB10Y": dict(name="UK 10-year gilt (long = long the bond)", asset_class="rates", country="United Kingdom",
                  currency="GBP", cost=0.001),
    "JP10Y": dict(name="Japan 10-year JGB (long = long the bond)", asset_class="rates", country="Japan", currency="JPY",
                  cost=0.001),
    "FR-DE": dict(name="France 10y OAT over the Bund (long = long OAT / short Bund, gains when the spread tightens)",
                  asset_class="rates spread", country="France", currency="EUR", cost=0.002),
    "EUR": dict(name="EUR/USD (long = long euro)", asset_class="fx", country="Euro area", currency="EUR", cost=0.001),
    "GBP": dict(name="GBP/USD (long = long sterling)", asset_class="fx", country="United Kingdom", currency="GBP", cost=0.001),
    "JPY": dict(name="USD/JPY quoted as JPY per USD (long = long yen)", asset_class="fx", country="Japan", currency="JPY",
                cost=0.001),
    "CHF": dict(name="USD/CHF quoted as CHF per USD (long = long Swiss franc)", asset_class="fx", country="Switzerland",
                currency="CHF", cost=0.001),
    "AUD": dict(name="AUD per USD (long = long Australian dollar)", asset_class="fx", country="Australia", currency="AUD",
                cost=0.001),
    "CAD": dict(name="CAD per USD (long = long Canadian dollar)", asset_class="fx", country="Canada", currency="CAD",
                cost=0.001),
}
DROPPED = [
    {"market": "Italy 10y spread over Germany (IT-DE)",
     "reason": "No free daily source: the ECB publishes country yields monthly only, Banca d'Italia's Infostat needs a "
               "session and the Riksbank publishes no Italian series. Only a monthly average is available, which can "
               "neither enter nor stop a position."},
    {"market": "Metals (gold, silver, copper, platinum, palladium)",
     "reason": "No free daily public price: LBMA, LME and COMEX data are licensed; FRED's LBMA gold series and the "
               "Bundesbank's gold price are discontinued; Yahoo and Stooq are blocked or rate-limited from the runners."},
    {"market": "Grains and oilseeds (corn, wheat, soybeans)",
     "reason": "No free daily futures settlement (CME data are licensed); USDA cash bids are not the contracts."},
    {"market": "Commodity futures settlements",
     "reason": "EIA stopped publishing NYMEX futures prices in April 2024. The five energy markets kept are marked on "
               "official spot prices (EIA via FRED) as an estimate of the front month; every page labels them so."},
    {"market": "Norgate and em-macro-data",
     "reason": "Licence: never used for Janus."},
]
# approximate notice/last-trade date of a contract for delivery month (y, m)
NOTICE_RULES = {
    "WTI": "20th of the month before delivery (CL last trade: 3 business days before the 25th)",
    "BRENT": "last day of the second month before delivery (ICE Brent last trade)",
    "NATGAS": "26th of the month before delivery (NG last trade: 3 business days before the 1st)",
    "HEATOIL": "last day of the month before delivery (HO last trade)",
    "RBOB": "last day of the month before delivery (RB last trade)",
}


def _add_months(y: int, m: int, k: int) -> tuple[int, int]:
    n = y * 12 + (m - 1) + k
    return n // 12, n % 12 + 1


def notice_date(inst: str, y: int, m: int) -> date:
    if inst == "WTI":
        py, pm = _add_months(y, m, -1)
        return date(py, pm, 20)
    if inst == "NATGAS":
        py, pm = _add_months(y, m, -1)
        return date(py, pm, 26)
    if inst == "BRENT":
        py, pm = _add_months(y, m, -2)
        return date(py, pm, calendar.monthrange(py, pm)[1])
    py, pm = _add_months(y, m, -1)
    return date(py, pm, calendar.monthrange(py, pm)[1])


def front_contract(inst: str, d: date) -> dict:
    """The earliest contract whose notice date is more than 35 days after ``d`` (T20-T22's buffer)."""
    y, m = d.year, d.month
    for k in range(0, 6):
        cy, cm = _add_months(y, m, k)
        nd = notice_date(inst, cy, cm)
        if nd > d + timedelta(days=ROLL_BUFFER_DAYS):
            code = f"{UNIVERSE[inst]['contract']}{MONTH_CODES[cm - 1]}{str(cy)[-2:]}"
            return {"code": code, "delivery": f"{cy}-{cm:02d}", "notice": nd.isoformat()}
    raise ValueError("no contract found")


def roll_rule_text(inst: str) -> str:
    return (f"Hold the earliest {UNIVERSE[inst]['exchange']} {UNIVERSE[inst]['contract']} contract whose notice date is more "
            f"than {ROLL_BUFFER_DAYS} days after the trade date; roll to the next one when the held contract is within "
            f"{ROLL_BEFORE_NOTICE_DAYS} days of its notice date (approximated as the {NOTICE_RULES[inst]}). P&L is marked on "
            "the spot proxy, so roll yield is not captured; each roll is charged as two trades.")


# ----------------------------------------------------------------------------- records and chain
def _canon(rec: dict) -> str:
    return json.dumps({k: v for k, v in rec.items() if k != "hash"}, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def chain_hash(prev: str, rec: dict) -> str:
    return hashlib.sha256((prev + _canon(rec)).encode("utf-8")).hexdigest()


def load(path: Path = RECORDS) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append(records: list[dict], rec: dict, path: Path | None = RECORDS) -> dict:
    prev = records[-1]["hash"] if records else GENESIS
    rec = {**rec, "seq": len(records) + 1, "prev_hash": prev}
    rec["recorded_at"] = rec.get("recorded_at") or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rec["hash"] = chain_hash(prev, rec)
    records.append(rec)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n")
    return rec


def verify(records: list[dict]) -> dict:
    prev = GENESIS
    for i, r in enumerate(records, 1):
        if r.get("seq") != i:
            return {"ok": False, "n": len(records), "error": f"record {i}: sequence {r.get('seq')} out of order"}
        if r.get("prev_hash") != prev:
            return {"ok": False, "n": len(records), "error": f"record {i}: prev_hash does not match record {i - 1}"}
        if chain_hash(prev, r) != r.get("hash"):
            return {"ok": False, "n": len(records), "error": f"record {i}: content does not match its hash (edited)"}
        prev = r["hash"]
    return {"ok": True, "n": len(records), "head": prev, "error": None}


# ----------------------------------------------------------------------------- marks
def registry_rows() -> dict[str, dict]:
    return {r["instrument"]: r for r in load_registry()}


def series(marks_rows: list[dict], inst: str, actable_only: bool = True) -> list[tuple[date, float, dict]]:
    out = {}
    for m in marks_rows:
        if m.get("instrument") != inst or not m.get("value"):
            continue
        if actable_only and not mark_can_act(m):
            continue
        d = parse_date(m.get("date"))
        if d:
            out[d] = (d, float(m["value"]), m)
    return [out[k] for k in sorted(out)]


def kind(inst: str, reg: dict[str, dict]) -> str:
    return PX.kind_of(reg.get(inst, {}))


# ----------------------------------------------------------------------------- state
def account_start(records: list[dict]) -> dict | None:
    return next((r for r in records if r["type"] == "account_open"), None)


def positions(records: list[dict]) -> dict[str, dict]:
    """Every position's current state, rebuilt from the records."""
    pos: dict[str, dict] = {}
    for r in records:
        t, pid = r["type"], r.get("position_id")
        if t == "open":
            pos[pid] = {"id": pid, "open": r, "status": "pending", "stop": r["stop"], "stop_history": [],
                        "reviews": [], "rolls": [], "fill": None, "close": None, "close_request": None,
                        "opposition": None, "postmortem": None, "cancel": None}
        elif pid in pos:
            p = pos[pid]
            if t == "fill":
                p["fill"], p["status"] = r, "open"
            elif t == "cancel":
                p["cancel"], p["status"] = r, "cancelled"
            elif t == "stop_change":
                p["stop_history"].append(r)
                p["stop"] = r["new_stop"]
            elif t == "review":
                p["reviews"].append(r)
            elif t == "close_request":
                p["close_request"] = r
            elif t == "roll":
                p["rolls"].append(r)
            elif t == "close":
                p["close"], p["status"] = r, "closed"
            elif t == "opposition":
                p["opposition"] = r
            elif t == "postmortem":
                p["postmortem"] = r
    return pos


def _costs_pct(p: dict) -> float:
    c = 0.0
    if p.get("fill"):
        c += p["fill"].get("cost_pct", 0.0)
    for r in p.get("rolls", []):
        c += r.get("cost_pct", 0.0)
    if p.get("close"):
        c += p["close"].get("exit_cost_pct", 0.0)
    return c


def pnl_at(p: dict, level: float, reg: dict[str, dict]) -> dict:
    """Gross and net P&L (% of the starting account) if marked at ``level``."""
    f = p["fill"]
    k = kind(p["open"]["instrument"], reg)
    r = PX.position_return(k, p["open"]["direction"], f["entry_level"], level)
    gross = 100.0 * f["notional_frac"] * r
    return {"gross_pct": round(gross, 4), "net_pct": round(gross - _costs_pct(p), 4), "return": r}


def stop_on(p: dict, d: date) -> float:
    """The stop in force on date ``d``: the initial stop, then every tightening recorded on or before ``d``."""
    st = p["open"]["stop"]
    for sc in p["stop_history"]:
        sd = parse_date(sc["date"])
        if sd and sd <= d:
            st = sc["new_stop"]
    return st


def open_risk(pos: dict[str, dict]) -> float:
    return sum(p["open"]["risk_pct"] for p in pos.values() if p["status"] in ("pending", "open"))


# ----------------------------------------------------------------------------- costs and sizing
def one_way_cost(inst: str, level: float) -> float:
    u = UNIVERSE[inst]
    if u["asset_class"] == "commodity":
        c_raw = (3.0 + u["tick_value"]) / (level * u["multiplier"])
        return 2.0 * c_raw
    return u["cost"]


def size(inst: str, direction: str, risk_pct: float, entry: float, stop: float, reg: dict[str, dict],
         ref: dict[str, dict], vol: float | None = None) -> dict:
    """Notional for ``risk_pct`` at risk to the stop, cut to the capacity limits."""
    k = kind(inst, reg)
    sr = PX.stop_return(k, direction, entry, stop)
    if sr is None or sr >= 0:
        raise ValueError("stop is not on the losing side of the entry")
    notional_frac = (risk_pct / 100.0) / abs(sr)
    notional = notional_frac * ACCOUNT_USD
    price = entry if UNIVERSE[inst]["asset_class"] == "commodity" else None
    cap = CAP.max_notional(inst, ref, price)
    note = ""
    if cap is not None and notional > cap:
        note = (f"size cut from {risk_pct:.2f}% to {risk_pct * cap / notional:.2f}% at risk to pass the capacity checks "
                f"(notional US${notional / 1e6:,.0f}m above the cap US${cap / 1e6:,.0f}m)")
        risk_pct = risk_pct * cap / notional
        notional, notional_frac = cap, cap / ACCOUNT_USD
    chk = CAP.check(inst, 100 * notional_frac, ACCOUNT_USD, ref, vol, 100 * notional_frac, price)
    impact = (chk["impact_bp_trade"] or 0.0) / 1e4
    return {"risk_pct": round(risk_pct, 4), "notional_frac": notional_frac, "notional_usd": round(notional),
            "contracts": (round(notional / (entry * UNIVERSE[inst]["multiplier"])) if price else None),
            "stop_return": sr, "capacity": chk, "capacity_note": note, "impact_frac": impact,
            "one_way_cost": one_way_cost(inst, entry)}


# ----------------------------------------------------------------------------- daily processing
def process(records: list[dict], marks_rows: list[dict], today: date, path: Path | None = RECORDS) -> list[str]:
    """Fill pending orders, roll commodities, close on stop / horizon / close request. Returns log lines."""
    reg = registry_rows()
    ref = CAP.load_reference()
    log = []
    for pid, p in sorted(positions(records).items()):
        o = p["open"]
        inst, direction = o["instrument"], o["direction"]
        k = kind(inst, reg)
        ser = series(marks_rows, inst)
        if p["status"] == "pending":
            dd = parse_date(o["decision_date"])
            nxt = next((x for x in ser if x[0] >= dd and x[0] <= today), None)
            if not nxt:
                continue
            d, v, m = nxt
            if not PX.valid_stop(k, direction, v, p["stop"]):
                append(records, {"type": "cancel", "position_id": pid, "date": d.isoformat(), "level": v,
                                 "reason": f"the entry mark {v:g} ({d}) is already through the stop {p['stop']:g}; not opened"}, path)
                log.append(f"{pid} cancelled: entry mark through the stop")
                continue
            sz = size(inst, direction, o["risk_pct"], v, p["stop"], reg, ref, o.get("ann_vol_pct"))
            cost_frac = sz["one_way_cost"] + sz["impact_frac"]
            fill = {"type": "fill", "position_id": pid, "entry_date": d.isoformat(), "entry_level": v,
                    "mark_source": m.get("source"), "mark_url": m.get("source_url"),
                    "risk_pct": sz["risk_pct"], "notional_frac": sz["notional_frac"], "notional_usd": sz["notional_usd"],
                    "contracts": sz["contracts"], "one_way_cost": sz["one_way_cost"], "impact_frac": sz["impact_frac"],
                    "cost_pct": round(100 * sz["notional_frac"] * cost_frac, 5),
                    "capacity": {k2: sz["capacity"][k2] for k2 in ("pct_adv", "adv_usd", "adv_status", "pct_limit",
                                                                   "position_limit", "impact_bp_trade", "flags")},
                    "capacity_note": sz["capacity_note"]}
            if UNIVERSE[inst]["asset_class"] == "commodity":
                fill["contract"] = front_contract(inst, d)
                fill["roll_rule"] = roll_rule_text(inst)
            append(records, fill, path)
            log.append(f"{pid} filled {direction} {inst} at {v:g} ({d}); notional US${sz['notional_usd'] / 1e6:,.1f}m")
            p = positions(records)[pid]
        if p["status"] != "open":
            continue
        f = p["fill"]
        ed = parse_date(f["entry_date"])
        after = [x for x in ser if ed < x[0] <= today]
        # commodity rolls (cost only; P&L is on the spot proxy)
        if UNIVERSE[inst]["asset_class"] == "commodity":
            held = (p["rolls"][-1]["to_contract"] if p["rolls"] else f["contract"])
            for d, v, _m in after:
                if d >= parse_date(held["notice"]) - timedelta(days=ROLL_BEFORE_NOTICE_DAYS):
                    nxt_c = front_contract(inst, d)
                    c = 2.0 * (one_way_cost(inst, v) + f.get("impact_frac", 0.0))
                    append(records, {"type": "roll", "position_id": pid, "date": d.isoformat(), "level": v,
                                     "from_contract": held, "to_contract": nxt_c,
                                     "cost_pct": round(100 * f["notional_frac"] * c, 5)}, path)
                    log.append(f"{pid} rolled {held['code']} -> {nxt_c['code']} on {d}")
                    held = nxt_c
        reason, hit = None, None
        hz = parse_date(o["horizon"])
        cr = parse_date((p.get("close_request") or {}).get("date"))
        for d, v, m in after:
            stop_now = stop_on(p, d)
            if PX.stop_hit(k, direction, f["entry_level"], stop_now, v):
                reason, hit = "stop", (d, v, m)
                break
            if cr and d >= cr:
                reason, hit = "Janus close decision", (d, v, m)
                break
            if hz and d >= hz:
                reason, hit = "horizon", (d, v, m)
                break
        if hit:
            d, v, m = hit
            pnl = pnl_at(p, v, reg)
            exit_cost = 100 * f["notional_frac"] * (one_way_cost(inst, v) + f.get("impact_frac", 0.0))
            gross = pnl["gross_pct"]
            net = round(gross - _costs_pct(p) - exit_cost, 4)
            append(records, {"type": "close", "position_id": pid, "date": d.isoformat(), "exit_level": v,
                             "reason": reason, "mark_source": m.get("source"), "gross_pnl_pct": gross,
                             "exit_cost_pct": round(exit_cost, 5), "net_pnl_pct": net,
                             "outcome": "right" if gross > 0 else "wrong",
                             "days_held": (d - ed).days}, path)
            log.append(f"{pid} closed ({reason}) at {v:g} on {d}: gross {gross:+.3f}%, net {net:+.3f}%")
    return log


# ----------------------------------------------------------------------------- summary for the app
def summarize(records: list[dict], marks_rows: list[dict], today: date | None = None) -> dict:
    today = today or date.today()
    reg = registry_rows()
    pos = positions(records)
    start = account_start(records)
    rows, closed = [], []
    for pid, p in sorted(pos.items()):
        o = p["open"]
        inst = o["instrument"]
        ser_all = series(marks_rows, inst, actable_only=False)
        last = ser_all[-1] if ser_all else None
        row = {"id": pid, "status": p["status"], "instrument": inst, "name": UNIVERSE.get(inst, {}).get("name", inst),
               "asset_class": UNIVERSE.get(inst, {}).get("asset_class"), "country": UNIVERSE.get(inst, {}).get("country"),
               "currency": UNIVERSE.get(inst, {}).get("currency"), "estimate": bool(UNIVERSE.get(inst, {}).get("estimate")),
               "direction": o["direction"], "risk_pct": (p["fill"] or o).get("risk_pct", o["risk_pct"]),
               "requested_risk_pct": o["risk_pct"], "stop": p["stop"], "initial_stop": o["stop"],
               "horizon": o["horizon"], "probability": o["probability"], "thesis": o["thesis"],
               "change_mind": o["change_mind"], "sources": o.get("sources", []), "sources_read": o.get("sources_read", []),
               "model": o["model"], "decided_at": o["decided_at"], "decision_date": o["decision_date"],
               "unit": reg.get(inst, {}).get("unit"), "opposition": (p["opposition"] or {}).get("opposition"),
               "opposition_model": (p["opposition"] or {}).get("model"),
               "reviews": [{"date": r["date"], "action": r["action"], "reasoning": r["reasoning"]} for r in p["reviews"]],
               "stop_history": [{"date": r["date"], "from": r["old_stop"], "to": r["new_stop"], "reasoning": r.get("reasoning")}
                                for r in p["stop_history"]],
               "rolls": [{"date": r["date"], "from": r["from_contract"]["code"], "to": r["to_contract"]["code"]} for r in p["rolls"]],
               "fill": p["fill"], "close": p["close"], "cancel": p["cancel"],
               "postmortem": (p["postmortem"] or {}).get("postmortem"),
               "mark": last[1] if last else None, "mark_date": last[0].isoformat() if last else None,
               "mark_flag": None if (last and mark_can_act(last[2])) else "no first-hand daily mark yet"}
        if p["fill"]:
            f = p["fill"]
            lvl = p["close"]["exit_level"] if p["close"] else (last[1] if last else None)
            if lvl is not None:
                pn = pnl_at(p, lvl, reg)
                row.update({"gross_pnl_pct": pn["gross_pct"], "net_pnl_pct": (p["close"] or {}).get("net_pnl_pct", pn["net_pct"]),
                            "return_pct": round(100 * pn["return"], 3)})
            k = kind(inst, reg)
            if not p["close"] and last:
                cur = PX.position_return(k, o["direction"], f["entry_level"], last[1])
                st = PX.stop_return(k, o["direction"], f["entry_level"], p["stop"])
                row["distance_to_stop_pct_account"] = round(100 * f["notional_frac"] * (cur - st), 4)
            hist = [(d.isoformat(), v) for d, v, _ in ser_all if d >= parse_date(f["entry_date"]) - timedelta(days=10)]
            row["mark_history"] = hist
        rows.append(row)
        if p["close"]:
            closed.append(row)
    n_closed = len(closed)
    right = sum(1 for c in closed if c["close"]["outcome"] == "right")
    briers = [((c["probability"] / 100.0) - (1.0 if c["close"]["outcome"] == "right" else 0.0)) ** 2 for c in closed]
    probs = [r["probability"] / 100.0 for r in rows if r["status"] in ("open", "closed", "pending")]
    pbar = sum(probs) / len(probs) if probs else 0.6
    need = calls_needed(pbar)
    eq = equity(records, marks_rows, today)
    bench = benchmark(records, marks_rows, today)
    open_rows = [r for r in rows if r["status"] in ("open", "pending")]
    return {
        "start": start, "account_usd": ACCOUNT_USD, "model": next((r["model"] for r in reversed(records) if r.get("model")), None),
        "positions": rows, "open": open_rows, "closed": closed,
        "no_trades": [{"date": r["date"], "reasoning": r["reasoning"], "model": r.get("model"), "decided_at": r.get("decided_at")}
                      for r in records if r["type"] == "no_trade"],
        "runs": [{k: r.get(k) for k in ("date", "decided_at", "model", "market_summary", "n_new", "n_reviews", "usage",
                                          "searches", "status")} for r in records if r["type"] == "run"],
        "risk_used_pct": round(open_risk(positions(records)), 3), "risk_limit_pct": MAX_RISK_TOTAL,
        "max_risk_pos_pct": MAX_RISK_POS, "max_open": MAX_OPEN, "n_open": len(open_rows),
        "hit_rate": round(100 * right / n_closed, 1) if n_closed else None, "n_closed": n_closed, "n_right": right,
        "brier": round(sum(briers) / len(briers), 4) if briers else None,
        "calls_needed": need, "mean_probability": round(100 * pbar, 1),
        "significance_method": (f"Resolved calls needed before the hit rate is statistically meaningful: one-sided binomial "
                                f"test of the hit rate against 50% at the 5% level with 80% power, if Janus's true hit rate "
                                f"equalled its average stated probability ({100 * pbar:.0f}%): n = ((1.645 x 0.5 + 0.842 x "
                                f"sqrt(p(1-p))) / (p - 0.5))^2 = {need}. A call is resolved when its position closes; it is "
                                f"right when the gross P&L (before costs) is positive."),
        "equity": eq, "benchmark": bench,
        "universe": [{"instrument": k, **{kk: vv for kk, vv in v.items() if kk not in ("tick_value",)},
                      "unit": reg.get(k, {}).get("unit"), "source": reg.get(k, {}).get("source"),
                      "source_id": reg.get(k, {}).get("source_id"), "source_url": reg.get(k, {}).get("source_url"),
                      "notes": reg.get(k, {}).get("notes"),
                      "roll_rule": roll_rule_text(k) if v["asset_class"] == "commodity" else None}
                     for k, v in UNIVERSE.items()],
        "dropped": DROPPED, "chain": verify(records),
        "disclaimer": ("Janus is an experiment in AI judgement. Its results do not feed the algorithm (v1.0 and v1.1 are "
                       "mechanical rules and never read Janus's records), and no edge is claimed."),
    }


def calls_needed(p: float, z_a: float = 1.645, z_b: float = 0.842) -> int | None:
    if p <= 0.5:
        return None
    return int(math.ceil(((z_a * 0.5 + z_b * math.sqrt(p * (1 - p))) / (p - 0.5)) ** 2))


def _dates(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _level_on(ser: list[tuple], d: date):
    best = None
    for x in ser:
        if x[0] <= d:
            best = x
        else:
            break
    return best


def equity(records: list[dict], marks_rows: list[dict], today: date) -> list[list]:
    """[[date, index]] daily from the account start: 100 + net P&L (% of the starting account), positions marked
    at the latest daily mark on or before each date (carried forward on days without one)."""
    start = account_start(records)
    if not start:
        return []
    reg = registry_rows()
    sd = parse_date(start["date"])
    pos = positions(records)
    sers = {p["open"]["instrument"]: series(marks_rows, p["open"]["instrument"]) for p in pos.values()}
    out = []
    for d in _dates(sd, today):
        total = 0.0
        for p in pos.values():
            f = p["fill"]
            if not f or parse_date(f["entry_date"]) > d:
                continue
            if p["close"] and parse_date(p["close"]["date"]) <= d:
                total += p["close"]["net_pnl_pct"]
                continue
            lv = _level_on(sers[p["open"]["instrument"]], d)
            if lv is None:
                continue
            gross = pnl_at(p, lv[1], reg)["gross_pct"]
            costs = f.get("cost_pct", 0.0) + sum(r.get("cost_pct", 0.0) for r in p["rolls"] if parse_date(r["date"]) <= d)
            total += gross - costs
        out.append([d.isoformat(), round(100.0 + total, 4)])
    return out


def benchmark(records: list[dict], marks_rows: list[dict], today: date) -> dict:
    """Equal-weight benchmark of the same instruments: each instrument Janus traded, held LONG over the same dates,
    every position at the same notional (the average of Janus's notionals), no costs. Janus minus this isolates the
    value of its direction and sizing choices."""
    reg = registry_rows()
    pos = [p for p in positions(records).values() if p["fill"]]
    if not pos:
        return {"pnl_pct": None, "janus_pnl_pct": None, "n": 0, "series": []}
    avg = sum(p["fill"]["notional_frac"] for p in pos) / len(pos)
    tot = 0.0
    for p in pos:
        inst = p["open"]["instrument"]
        ser = series(marks_rows, inst)
        exit_lv = p["close"]["exit_level"] if p["close"] else (ser[-1][1] if ser else None)
        if exit_lv is None:
            continue
        tot += 100 * avg * PX.ret_long(kind(inst, reg), p["fill"]["entry_level"], exit_lv)
    eq = equity(records, marks_rows, today)
    return {"pnl_pct": round(tot, 4), "janus_pnl_pct": round(eq[-1][1] - 100, 4) if eq else None, "n": len(pos),
            "method": "Equal-weight benchmark: the same instruments over the same dates, always long, each at Janus's "
                      "average notional, before costs."}


# ----------------------------------------------------------------------------- the weekly run
SYSTEM = """You are Janus, a discretionary macro portfolio manager running a PAPER account of US$500,000,000 for an experiment in AI judgement. Nothing you do feeds any other strategy. No edge is assumed: opening nothing is a legitimate, often correct, decision.

Each week you (1) review every open position and (2) may open new ones. Use the web_search tool to read current news, data releases, central-bank communication and prices before deciding. Cite the pages you relied on.

Hard rules (the code enforces them and will reject or cut anything that breaks them):
- Universe: ONLY the instruments listed in the request, by their exact code. Direction conventions are given per instrument ("long" = long the bond for yields; long the peripheral bond / short the Bund for FR-DE; long the named currency for FX; long the front-month future for commodities).
- Size is the % of the account lost if the stop is hit: at most 2.0 per position, at most 10.0 in total across open and new positions, at most 8 open positions.
- The stop is a level in the instrument's own unit (price, % yield, or bp), on the losing side of the current mark.
- For an open position you may only HOLD, CLOSE, or TIGHTEN its stop (move it closer to the current mark). Never widen a stop.
- Horizon: a date between 1 week and 6 months from today.
- Probability: your honest probability (0-100) that the position closes with a gain before costs. Calibrate: 50 means no view; above 70 is rare.
- Entry is at the next available daily official mark, not now; capacity limits (10% of daily volume) may cut size.

Reply with ONLY one JSON object, no prose before or after:
{"market_summary": "2-4 sentences on what matters this week",
 "reviews": [{"id": "J001", "action": "hold" | "close" | "tighten_stop", "new_stop": number or null, "reasoning": "1-3 sentences"}],
 "new_positions": [{"instrument": "CODE", "direction": "long" | "short", "risk_pct": number, "stop": number, "horizon": "YYYY-MM-DD", "probability": number, "thesis": "2-3 sentences", "change_mind": "what would change your mind, 1-2 sentences", "sources": [{"title": "...", "url": "https://..."}]}],
 "no_trade_reasoning": "required when new_positions is empty: why nothing meets the bar this week"}"""

OPPOSITION_SYSTEM = """You are The Opposition: an independent risk reviewer whose only job is to write the strongest honest case AGAINST a paper trade proposed by another model (Janus). Use the web_search tool to find evidence. Do not hedge or balance; argue against the position as well as it can be argued, with facts, and say what would prove the trade wrong quickly.

Reply with ONLY one JSON object:
{"case_against": "4-6 sentences", "key_risks": ["...", "..."], "what_proves_it_wrong": "1-2 sentences: the observable that would show Janus is wrong", "probability_view_wrong": number (0-100), "sources": [{"title": "...", "url": "https://..."}]}"""


def market_snapshot(marks_rows: list[dict], today: date) -> list[dict]:
    reg = registry_rows()
    out = []
    for inst, u in UNIVERSE.items():
        ser = series(marks_rows, inst, actable_only=False)
        if not ser:
            out.append({"instrument": inst, "name": u["name"], "mark": None})
            continue
        last = ser[-1]
        def ago(n):
            target = last[0] - timedelta(days=n)
            x = _level_on(ser, target)
            return x[1] if x else None
        row = {"instrument": inst, "name": u["name"], "unit": reg.get(inst, {}).get("unit"), "mark": last[1],
               "mark_date": last[0].isoformat(), "level_1w_ago": ago(7), "level_1m_ago": ago(30),
               "estimate": bool(u.get("estimate"))}
        if u["asset_class"] == "commodity":
            row["front_contract"] = front_contract(inst, today)["code"]
        out.append(row)
    return out


def build_prompt(records: list[dict], marks_rows: list[dict], today: date) -> str:
    reg = registry_rows()
    pos = positions(records)
    snap = market_snapshot(marks_rows, today)
    open_rows = []
    for pid, p in sorted(pos.items()):
        if p["status"] not in ("open", "pending"):
            continue
        o = p["open"]
        ser = series(marks_rows, o["instrument"], actable_only=False)
        row = {"id": pid, "instrument": o["instrument"], "direction": o["direction"], "risk_pct": o["risk_pct"],
               "stop": p["stop"], "horizon": o["horizon"], "probability": o["probability"], "thesis": o["thesis"],
               "status": p["status"], "latest_mark": ser[-1][1] if ser else None}
        if p["fill"]:
            row.update(entry=p["fill"]["entry_level"], entry_date=p["fill"]["entry_date"],
                       pnl_pct_of_account=pnl_at(p, ser[-1][1], reg)["net_pct"] if ser else None)
        open_rows.append(row)
    closed = [{"id": pid, "instrument": p["open"]["instrument"], "direction": p["open"]["direction"],
               "outcome": p["close"]["outcome"], "net_pnl_pct": p["close"]["net_pnl_pct"], "reason": p["close"]["reason"]}
              for pid, p in sorted(pos.items()) if p["close"]][-10:]
    eq = equity(records, marks_rows, today)
    return (f"TODAY: {today.isoformat()} (weekly review)\n"
            f"ACCOUNT INDEX: {eq[-1][1] if eq else 100.0} (100 at the start); open risk {open_risk(pos):.2f}% of 10% allowed; "
            f"{sum(1 for p in pos.values() if p['status'] in ('open', 'pending'))} of 8 positions open.\n\n"
            f"UNIVERSE (latest official daily marks; 'estimate' = commodity marked on the official spot price):\n"
            f"{json.dumps(snap, indent=1)}\n\n"
            f"OPEN POSITIONS:\n{json.dumps(open_rows, indent=1) if open_rows else 'none'}\n\n"
            f"RECENTLY CLOSED:\n{json.dumps(closed, indent=1) if closed else 'none'}\n\n"
            "Review each open position, then decide whether to open new ones. Reply with the JSON object only.")


def validate(ans: dict, records: list[dict], marks_rows: list[dict], today: date) -> tuple[list[dict], list[dict], list[str]]:
    """Returns (reviews, new positions, rejections) after applying the hard rules."""
    reg = registry_rows()
    pos = positions(records)
    notes, reviews, new = [], [], []
    for r in ans.get("reviews") or []:
        pid = str(r.get("id", "")).strip()
        p = pos.get(pid)
        if not p or p["status"] not in ("open", "pending"):
            notes.append(f"review of {pid!r} ignored: not an open position")
            continue
        act = str(r.get("action", "hold")).lower()
        if act == "tighten_stop":
            o = p["open"]
            ref_level = p["fill"]["entry_level"] if p["fill"] else None
            ser = series(marks_rows, o["instrument"], actable_only=False)
            k = kind(o["instrument"], reg)
            try:
                ns = float(r.get("new_stop"))
            except (TypeError, ValueError):
                notes.append(f"{pid}: tighten_stop without a numeric new stop; held")
                act = "hold"
            else:
                base = ref_level if ref_level is not None else (ser[-1][1] if ser else None)
                old_r = PX.stop_return(k, o["direction"], base, p["stop"])
                new_r = PX.stop_return(k, o["direction"], base, ns)
                cur = ser[-1][1] if ser else None
                if new_r is None or old_r is None or new_r <= old_r + 1e-12:
                    notes.append(f"{pid}: new stop {ns} would widen (or not move) the stop {p['stop']}; rejected, held")
                    act = "hold"
                elif cur is not None and not PX.valid_stop(k, o["direction"], cur, ns):
                    notes.append(f"{pid}: new stop {ns} is already through the current mark {cur}; treated as a close")
                    act = "close"
                else:
                    r = {**r, "new_stop": ns}
        reviews.append({**r, "id": pid, "action": act})
    total = open_risk(pos)
    n_open = sum(1 for p in pos.values() if p["status"] in ("open", "pending"))
    closing = {r["id"] for r in reviews if r["action"] == "close"}
    for p in pos.values():
        if p["id"] in closing:
            total -= p["open"]["risk_pct"]
            n_open -= 1
    for n in ans.get("new_positions") or []:
        inst = str(n.get("instrument", "")).strip().upper()
        if inst not in UNIVERSE:
            notes.append(f"new position in {inst!r} rejected: not in the universe")
            continue
        direction = str(n.get("direction", "")).lower()
        if direction not in ("long", "short"):
            notes.append(f"{inst}: direction {direction!r} rejected")
            continue
        try:
            risk, stop, prob = float(n.get("risk_pct")), float(n.get("stop")), float(n.get("probability"))
        except (TypeError, ValueError):
            notes.append(f"{inst}: risk, stop or probability not numeric; rejected")
            continue
        hz = parse_date(n.get("horizon"))
        if not hz or not (today + timedelta(days=MIN_HORIZON_DAYS) <= hz <= today + timedelta(days=MAX_HORIZON_DAYS)):
            notes.append(f"{inst}: horizon {n.get('horizon')} outside 1 week to 6 months; rejected")
            continue
        if not (0 < prob <= 100):
            notes.append(f"{inst}: probability {prob} rejected")
            continue
        ser = series(marks_rows, inst, actable_only=False)
        if not ser:
            notes.append(f"{inst}: no mark; rejected")
            continue
        cur = ser[-1][1]
        if not PX.valid_stop(kind(inst, reg), direction, cur, stop):
            notes.append(f"{inst}: stop {stop} is not on the losing side of the current mark {cur}; rejected")
            continue
        if n_open >= MAX_OPEN:
            notes.append(f"{inst}: already {MAX_OPEN} positions; rejected")
            continue
        risk = min(risk, MAX_RISK_POS)
        if total + risk > MAX_RISK_TOTAL + 1e-9:
            if MAX_RISK_TOTAL - total < 0.1:
                notes.append(f"{inst}: total risk limit {MAX_RISK_TOTAL}% reached; rejected")
                continue
            notes.append(f"{inst}: risk cut from {risk}% to {MAX_RISK_TOTAL - total:.2f}% (10% total limit)")
            risk = round(MAX_RISK_TOTAL - total, 2)
        # provisional capacity check at the current mark (the fill re-checks at the entry mark)
        sz = size(inst, direction, risk, cur, stop, reg, CAP.load_reference())
        if sz["capacity_note"]:
            notes.append(f"{inst}: {sz['capacity_note']}")
            risk = sz["risk_pct"]
        total += risk
        n_open += 1
        new.append({**n, "instrument": inst, "direction": direction, "risk_pct": round(risk, 4), "stop": stop,
                    "probability": prob, "horizon": hz.isoformat(), "provisional_capacity": sz["capacity"]})
    return reviews, new, notes


def next_id(records: list[dict]) -> str:
    n = sum(1 for r in records if r["type"] == "open")
    return f"J{n + 1:03d}"


def run(today: date | None = None, now: datetime | None = None, ask=None, oppose=None, path: Path | None = RECORDS,
        marks_rows: list[dict] | None = None) -> dict:
    """The weekly review. ``ask``/``oppose`` (tests) replace the API calls: f(system, prompt) -> llm.call dict."""
    from . import llm
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    today = today or now.date()
    marks_rows = marks_rows if marks_rows is not None else read_marks()
    records = load(path) if path else []
    if not account_start(records):
        append(records, {"type": "account_open", "date": today.isoformat(), "account_usd": ACCOUNT_USD, "index": 100.0,
                         "rules": {"max_risk_position_pct": MAX_RISK_POS, "max_risk_total_pct": MAX_RISK_TOTAL,
                                   "max_open": MAX_OPEN, "capacity_max_pct_adv": CAP.MAX_PCT_ADV,
                                   "stops": "tighten only", "entry": "next available first-hand daily mark"},
                         "universe": sorted(UNIVERSE), "dropped": [d["market"] for d in DROPPED],
                         "note": "Janus paper account opened: US$500,000,000, reported in % (index 100)."}, path)
    process(records, marks_rows, today, path)       # bring fills and closes up to date first
    call = ask or (lambda s, p: llm.call(s, p, purpose="janus run", ref=today.isoformat(), effort="high",
                                         web_search=int(llm.CONFIG.get("janus_web_searches", 12))))
    prompt = build_prompt(records, marks_rows, today)
    res = call(SYSTEM, prompt)
    ans = llm.parse_json(res.get("text", ""), "reviews") or llm.parse_json(res.get("text", ""), "new_positions")
    if ans is None:
        append(records, {"type": "run", "date": today.isoformat(), "decided_at": now.isoformat(), "model": res.get("model"),
                         "status": f"no usable answer ({res.get('status')})", "raw": (res.get("text") or "")[:4000],
                         "usage": res.get("usage"), "searches": res.get("searches"), "n_new": 0, "n_reviews": 0}, path)
        return {"ok": False, "reason": "no JSON answer", "records": records}
    reviews, new, notes = validate(ans, records, marks_rows, today)
    run_rec = append(records, {"type": "run", "date": today.isoformat(), "decided_at": now.isoformat(),
                               "model": res.get("model"), "status": res.get("status"),
                               "market_summary": ans.get("market_summary"), "usage": res.get("usage"),
                               "searches": res.get("searches"), "request_id": res.get("request_id"),
                               "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                               "n_new": len(new), "n_reviews": len(reviews), "rule_notes": notes,
                               "sources_read": res.get("sources_read", [])[:40]}, path)
    pos = positions(records)
    for r in reviews:
        p = pos[r["id"]]
        base = {"position_id": r["id"], "date": today.isoformat(), "decided_at": now.isoformat(),
                "model": res.get("model"), "reasoning": r.get("reasoning", ""), "run_seq": run_rec["seq"]}
        append(records, {"type": "review", "action": r["action"], **base}, path)
        if r["action"] == "tighten_stop":
            append(records, {"type": "stop_change", "old_stop": p["stop"], "new_stop": r["new_stop"], **base}, path)
        elif r["action"] == "close":
            if p["status"] == "pending":
                append(records, {"type": "cancel", "position_id": r["id"], "date": today.isoformat(),
                                 "reason": "Janus closed the order before it was filled"}, path)
            else:
                append(records, {"type": "close_request", **base}, path)
    opened = []
    for n in new:
        pid = next_id(records)
        rec = append(records, {"type": "open", "position_id": pid, "instrument": n["instrument"], "direction": n["direction"],
                               "risk_pct": n["risk_pct"], "requested_risk_pct": n.get("risk_pct"), "stop": n["stop"],
                               "horizon": n["horizon"], "probability": n["probability"],
                               "thesis": " ".join(str(n.get("thesis", "")).split()),
                               "change_mind": " ".join(str(n.get("change_mind", "")).split()),
                               "sources": n.get("sources") or [], "sources_read": res.get("sources_read", [])[:25],
                               "model": res.get("model"), "decided_at": now.isoformat(), "decision_date": today.isoformat(),
                               "entry_rule": "next available first-hand daily mark dated on or after the decision date",
                               "provisional_capacity": n.get("provisional_capacity"), "run_seq": run_rec["seq"]}, path)
        opened.append(rec)
    if not opened:
        append(records, {"type": "no_trade", "date": today.isoformat(), "decided_at": now.isoformat(),
                         "model": res.get("model"), "run_seq": run_rec["seq"],
                         "reasoning": " ".join(str(ans.get("no_trade_reasoning") or ans.get("market_summary") or
                                                   "No reasoning given.").split()),
                         "rule_notes": notes}, path)
    # The Opposition: a second, independent call per new position
    opp = oppose or (lambda s, p: llm.call(s, p, purpose="janus opposition", ref=p[:40], effort="high",
                                           web_search=int(llm.CONFIG.get("opposition_web_searches", 6))))
    for rec in opened:
        prompt = (f"TODAY: {today.isoformat()}\nPROPOSED PAPER POSITION ({rec['position_id']}):\n"
                  + json.dumps({k: rec[k] for k in ("instrument", "direction", "risk_pct", "stop", "horizon", "probability",
                                                     "thesis", "change_mind")}, indent=1)
                  + f"\nINSTRUMENT: {UNIVERSE[rec['instrument']]['name']}\n\nWrite the strongest case against it. JSON only.")
        o = opp(OPPOSITION_SYSTEM, prompt)
        oj = llm.parse_json(o.get("text", ""), "case_against") or {"case_against": (o.get("text") or "").strip()[:3000]}
        oj.setdefault("sources_read", o.get("sources_read", [])[:15])
        append(records, {"type": "opposition", "position_id": rec["position_id"], "date": today.isoformat(),
                         "model": o.get("model"), "decided_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                         "opposition": oj, "usage": o.get("usage")}, path)
    return {"ok": True, "opened": [r["position_id"] for r in opened], "reviews": reviews, "notes": notes,
            "records": records}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "mark", "verify", "status"])
    ap.add_argument("--today", default=None)
    a = ap.parse_args(argv)
    today = parse_date(a.today) if a.today else date.today()
    if a.cmd == "verify":
        v = verify(load())
        print(json.dumps(v))
        return 0 if v["ok"] else 1
    if a.cmd == "mark":
        recs = load()
        if not recs:
            print("no Janus records yet")
            return 0
        for line in process(recs, read_marks(), today):
            print(line)
        print(json.dumps(verify(recs)))
        return 0
    if a.cmd == "status":
        s = summarize(load(), read_marks(), today)
        print(json.dumps({k: s[k] for k in ("risk_used_pct", "n_open", "n_closed", "hit_rate", "brier", "calls_needed")}))
        for p in s["positions"]:
            print(p["id"], p["status"], p["direction"], p["instrument"], p["risk_pct"], p.get("net_pnl_pct"))
        return 0
    from .llm import KeyRejected
    try:
        res = run(today=today if a.today else None)
    except KeyRejected as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2
    print(json.dumps({k: v for k, v in res.items() if k != "records"}, indent=1, default=str))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
