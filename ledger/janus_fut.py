"""Janus's futures by contract month and defined-risk option spreads (ledger/janus.py calls in here).

**Marks.** Final daily settlements of the held contract month from Databento (ledger/settlements.py), stored only
in the private repository em-macro-data. ICE Brent is held and marked as NYMEX BZ of the same month, flagged as a
proxy.

**What is public.** Janus's records (data/janus/records.jsonl) never contain a settlement, a fill or exit price, a
model value, a notional or a contract count. A fill, roll or close records its date, the contract, the % at risk,
the costs and P&L in % of the account, and ``entry_digest`` = SHA-256 of "code|date|price". The digest lets anyone
holding the private settlements check the price that was used. Daily P&L in % goes to data/janus/futures_pnl.csv.
Everything else is recomputed from the private settlements whenever they are available (the daily run and any
session with em-macro-data checked out).

**Futures.**
- Fill at the first final settlement of the contract on or after the decision date.
- Notional = % at risk / |stop return|, cut to the capacity limits (10% of ADV, below 80% of the position limit).
- Hold the earliest listed contract whose notice date is more than 35 days after the trade date. Roll at that
  day's settlements when it comes within 10 days of its notice date, keeping the same notional. Each roll is
  charged as two trades.
- P&L = notional x the sum of the legs' returns (roll yield included).
- The stop is a level of the contract held when it was set. It acts on the position's cumulative return, so a
  roll does not move it.

**Options (defined risk only).**
- Allowed structures: a long call or put, or a debit or credit vertical on one contract month.
- Valued like the Me book's options: Black-76 on the underlying's final settlement, with the implied volatility
  Janus states at entry (with its source, or "estimate"). The fill is the model value at the first settlement on
  or after the decision date, labelled a model estimate.
- Maximum loss per unit = the premium (debit), or width - credit (credit). % at risk = that maximum loss.
- Closes on a settlement through the stop (an underlying level), at the horizon, or at expiry (intrinsic value).

**Costs.** Per contract per side: 2 x (US$3 + one tick), as for the T20-T22 model, for every leg. The square-root
impact estimate is added for futures.
"""
from __future__ import annotations

import csv
import hashlib
from datetime import date, timedelta
from pathlib import Path

from . import capacity as CAP
from . import derivs as DV
from . import settlements as ST

PNL_FILE = "data/janus/futures_pnl.csv"
PNL_COLUMNS = ["date", "position_id", "gross_pct", "costs_pct", "net_pct", "basis", "contract", "proxy"]
ROLL_BUFFER_DAYS, ROLL_BEFORE_NOTICE_DAYS = 35, 10
OPTION_STRUCTURES = ("call", "put", "call spread", "put spread")


def digest(code: str, d: date | str, price: float) -> str:
    return hashlib.sha256(f"{code}|{d}|{price:.10g}".encode()).hexdigest()


def contract(prod: str, month: str) -> dict:
    y, m = int(month[:4]), int(month[5:7])
    return {"month": month, "code": ST.contract_code(prod, month), "notice": ST.notice_date(prod, y, m).isoformat()}


def front(prod: str, d: date) -> dict:
    return contract(prod, ST.front_month(prod, d, ROLL_BUFFER_DAYS))


def roll_rule_text(prod: str) -> str:
    c = ST.CONTRACTS[prod]
    return (f"Hold the earliest listed {c['exchange']} {c['root']} contract whose notice date is more than "
            f"{ROLL_BUFFER_DAYS} days after the trade date; roll at that day's final settlements when the held "
            f"contract is within {ROLL_BEFORE_NOTICE_DAYS} days of its notice date ({ST.NOTICE_TEXT[c['notice']]}). "
            "P&L is on the held contracts, so roll yield is included; each roll is charged as two trades.")


def exact(rows: list[dict], prod: str, month: str, d: date) -> float | None:
    for x in ST.series(rows, prod, month):
        if x[0] == d:
            return x[1]
    return None


def one_way_cost(prod: str, price: float) -> float:
    c = ST.CONTRACTS[prod]
    return 2.0 * (3.0 + c["tick_value"]) / (price * c["multiplier"])


def sign(direction: str) -> float:
    return -1.0 if direction == "short" else 1.0


# ----------------------------------------------------------------------------- options
def option_spec(o: dict) -> dict | None:
    return o.get("option") or None


def option_value(spec: dict, F: float, d: date) -> tuple[float, str]:
    legs = DV.legs_from_text(spec["legs"])
    expiry = date.fromisoformat(spec["expiry"])
    if d >= expiry:
        return sum(l["q"] * DV.intrinsic(l["kind"], F, l["strike"]) for l in legs), "intrinsic at expiry"
    return (DV.structure_value(legs, F, DV.year_frac(d, expiry), spec["iv_pct"] / 100, spec["rate_pct"] / 100),
            DV.MODEL_LABEL)


def option_delta_up(spec: dict, F: float, d: date) -> bool:
    legs = DV.legs_from_text(spec["legs"])
    T = max(DV.year_frac(d, date.fromisoformat(spec["expiry"])), 1 / 365)
    iv, r = spec["iv_pct"] / 100, spec["rate_pct"] / 100
    return DV.structure_value(legs, F * 1.01, T, iv, r) > DV.structure_value(legs, F, T, iv, r)


def check_option(n: dict, prod: str, month: str, F: float | None, today: date, horizon: date | None,
                 stop: float | None, r_pct: float) -> tuple[dict | None, list[str]]:
    """(option spec, errors) for a proposal's ``option`` block: defined-risk structures only."""
    errs = []
    o = n.get("option") or {}
    legs = DV.parse_legs(str(o.get("legs") or ""))
    st = DV.classify(legs) if legs else "other"
    if st not in OPTION_STRUCTURES:
        return None, ["option.legs must be a long call or put, or a vertical spread (e.g. 'long 110 call, short 130 call')"]
    expiry = DV.parse_date(str(o.get("expiry") or ""))
    if not expiry:
        errs.append("option.expiry (a date) is required")
    else:
        y, m = int(month[:4]), int(month[5:7])
        if expiry <= today:
            errs.append("option.expiry must be in the future")
        elif expiry >= ST.notice_date(prod, y, m):
            errs.append(f"option.expiry {expiry} must be before the {month} contract's notice date")
        if horizon and horizon > expiry:
            errs.append(f"horizon {horizon} is after the option expiry {expiry}")
    try:
        iv = float(o.get("iv_pct"))
    except (TypeError, ValueError):
        iv = None
    src = " ".join(str(o.get("iv_source") or "").split())
    if iv is None or not (1 <= iv <= 300):
        errs.append("option.iv_pct (implied volatility, % a year, 1-300) is required")
    if not src:
        errs.append("option.iv_source is required: where the implied volatility comes from, or 'estimate'")
    if errs:
        return None, errs
    spec = {"structure": st, "legs": DV.legs_text(legs), "expiry": expiry.isoformat(), "iv_pct": iv,
            "iv_source": src, "rate_pct": r_pct}
    if F is not None:
        v0, _ = option_value(spec, F, today)
        rpu, err = DV.risk_per_unit(legs, round(v0, 10), F, stop)
        if err:
            return None, [err]
        if rpu is None or rpu <= 0:
            return None, ["the structure has no defined maximum loss"]
        if stop is not None:
            up = option_delta_up(spec, F, today)
            if (up and stop >= F) or (not up and stop <= F):
                return None, [f"stop {stop:g} (an underlying level) is on the winning side of the current settlement"]
    return spec, []


# ----------------------------------------------------------------------------- position state from the store
def legs_of(p: dict) -> list[dict]:
    """The held contracts: [{'month', 'start'}] from the fill and the rolls."""
    f = p["fill"]
    out = [{"month": f["contract"]["month"], "start": date.fromisoformat(f["entry_date"])}]
    for r in p["rolls"]:
        out.append({"month": r["to_contract"]["month"], "start": date.fromisoformat(r["date"])})
    return out


def leg_returns(p: dict, rows: list[dict], prod: str, d: date) -> tuple[list[float], dict | None, float | None]:
    """(returns of each leg up to ``d``, the leg held at ``d``, its start price)."""
    legs = legs_of(p)
    rets, cur, cur_start = [], None, None
    for i, leg in enumerate(legs):
        if leg["start"] > d:
            break
        p0 = exact(rows, prod, leg["month"], leg["start"])
        end = legs[i + 1]["start"] if i + 1 < len(legs) and legs[i + 1]["start"] <= d else d
        x = ST.on_or_before(rows, prod, leg["month"], end)
        if p0 is None or x is None:
            rets.append(0.0)
        else:
            rets.append(sign(p["open"]["direction"]) * (x[1] / p0 - 1))
        cur, cur_start = leg, p0
    return rets, cur, cur_start


def notional_frac(p: dict, rows: list[dict], prod: str) -> float | None:
    f = p["fill"]
    F0 = exact(rows, prod, f["contract"]["month"], date.fromisoformat(f["entry_date"]))
    if F0 is None:
        return None
    sr = sign(p["open"]["direction"]) * (p["open"]["stop"] - F0) / F0
    return (f["risk_pct"] / 100.0) / abs(sr) if sr else None


def threshold(p: dict, rows: list[dict], prod: str, d: date) -> float | None:
    """The stop in force on ``d`` as a cumulative-return threshold (negative)."""
    f = p["fill"]
    F0 = exact(rows, prod, f["contract"]["month"], date.fromisoformat(f["entry_date"]))
    if F0 is None:
        return None
    s = sign(p["open"]["direction"])
    thr = s * (p["open"]["stop"] - F0) / F0
    for sc in p["stop_history"]:
        sd = date.fromisoformat(sc["date"])
        if sd > d:
            continue
        rets, cur, p_start = leg_returns(p, rows, prod, sd)
        if p_start:
            thr = sum(rets[:-1]) + s * (sc["new_stop"] - p_start) / p_start
    return thr


def option_state(p: dict, rows: list[dict], prod: str, d: date) -> tuple[float | None, str | None, float | None]:
    """(value per unit, basis, underlying settlement) on or before ``d``."""
    spec = p["fill"]["option"]
    x = ST.on_or_before(rows, prod, p["fill"]["contract"]["month"], min(d, date.fromisoformat(spec["expiry"])))
    if x is None:
        return None, None, None
    v, basis = option_value(spec, x[1], d if d < date.fromisoformat(spec["expiry"]) else date.fromisoformat(spec["expiry"]))
    return v, basis, x[1]


def option_entry(p: dict, rows: list[dict], prod: str) -> tuple[float | None, float | None]:
    """(entry value per unit, maximum loss per unit), recomputed from the entry settlement."""
    f = p["fill"]
    spec = f["option"]
    F0 = exact(rows, prod, f["contract"]["month"], date.fromisoformat(f["entry_date"]))
    if F0 is None:
        return None, None
    v0, _ = option_value(spec, F0, date.fromisoformat(f["entry_date"]))
    rpu, _err = DV.risk_per_unit(DV.legs_from_text(spec["legs"]), round(v0, 10), F0, None)
    return v0, rpu


def gross_pct(p: dict, rows: list[dict], prod: str, d: date) -> tuple[float | None, str]:
    if p["fill"].get("option"):
        v, basis, _ = option_state(p, rows, prod, d)
        v0, rpu = option_entry(p, rows, prod)
        if v is None or v0 is None or not rpu:
            return None, "no settlement"
        return round(p["fill"]["risk_pct"] * (v - v0) / rpu, 4), basis
    nf = notional_frac(p, rows, prod)
    if nf is None:
        return None, "no settlement"
    rets, _c, _s = leg_returns(p, rows, prod, d)
    return round(100 * nf * sum(rets), 4), "settlement"


def option_contracts(risk_pct: float, rpu: float, prod: str, account: float) -> float:
    return (risk_pct / 100.0) * account / (rpu * ST.CONTRACTS[prod]["multiplier"])


def option_side_cost_pct(n_spreads: float, n_legs: int, prod: str, account: float) -> float:
    return 100 * n_spreads * n_legs * 2.0 * (3.0 + ST.CONTRACTS[prod]["tick_value"]) / account


# ----------------------------------------------------------------------------- the public P&L file
def read_pnl(p: Path) -> list[dict]:
    """Rows of the public P&L file ``p`` (data/janus/futures_pnl.csv)."""
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_pnl(p: Path, rows: list[dict]) -> None:
    keyed = {(r["position_id"], r["date"]): r for r in read_pnl(p)}
    for r in rows:
        keyed[(r["position_id"], r["date"])] = r
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=PNL_COLUMNS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in sorted(keyed.values(), key=lambda r: (r["date"], r["position_id"])):
            w.writerow(r)


def pnl_on(pnl_rows: list[dict], pid: str, d: date) -> dict | None:
    best = None
    for r in pnl_rows:
        if r["position_id"] == pid and r["date"] <= d.isoformat() and (best is None or r["date"] >= best["date"]):
            best = r
    return best


# ----------------------------------------------------------------------------- daily processing
def process_position(p: dict, prod: str, rows: list[dict], today: date, ref: dict, account: float,
                     append, pnl_out: list[dict]) -> list[str]:
    """Fill / roll / close one Janus futures or options position from the private settlements. ``append(rec)``
    appends a record to the chain and returns it; ``pnl_out`` collects public P&L rows (% only)."""
    log: list[str] = []
    o, pid = p["open"], p["id"]
    c = ST.CONTRACTS[prod]
    is_opt = bool(o.get("option"))
    month = o["contract"]["month"]
    if p["status"] == "pending":
        dd = date.fromisoformat(o["decision_date"])
        nxt = next((x for x in ST.series(rows, prod, month) if dd <= x[0] <= today), None)
        if not nxt:
            return log
        d, F, _row = nxt
        base = {"type": "fill", "position_id": pid, "entry_date": d.isoformat(), "contract": o["contract"],
                "mark_source": f"{ST.SOURCE} ({c['exchange']} {c['root']})", "proxy": bool(c.get("proxy")),
                "entry_private": True, "entry_digest": digest(o["contract"]["code"], d, F)}
        if is_opt:
            spec = {**o["option"]}
            up = option_delta_up(spec, F, d)
            if (up and F <= o["stop"]) or (not up and F >= o["stop"]):
                append({"type": "cancel", "position_id": pid, "date": d.isoformat(),
                        "reason": "the entry settlement was already through the stop; not opened"})
                return log + [f"{pid} cancelled: entry settlement through the stop"]
            v0, _ = option_value(spec, F, d)
            rpu, err = DV.risk_per_unit(DV.legs_from_text(spec["legs"]), round(v0, 10), F, None)
            if err or not rpu:
                append({"type": "cancel", "position_id": pid, "date": d.isoformat(),
                        "reason": f"no defined maximum loss at the entry settlement ({err}); not opened"})
                return log + [f"{pid} cancelled: {err}"]
            risk = o["risk_pct"]
            n = option_contracts(risk, rpu, prod, account)
            delta_contracts = n * abs(DV.structure_value(DV.legs_from_text(spec["legs"]), F * 1.01,
                                                         max(DV.year_frac(d, date.fromisoformat(spec["expiry"])), 1 / 365),
                                                         spec["iv_pct"] / 100, spec["rate_pct"] / 100) - v0) / (0.01 * F)
            chk = CAP.check(o["instrument"], 100 * delta_contracts * F * c["multiplier"] / account, account, ref,
                            None, None, F)
            note = ""
            if chk["flags"] and set(chk["flags"]) & {"adv", "limit"}:
                note = "delta-equivalent size above the capacity limits; risk cut"
                cut = min([CAP.MAX_PCT_ADV / chk["pct_adv"] if chk.get("pct_adv") else 1.0,
                           100 * CAP.NEAR_LIMIT / chk["pct_limit"] * 0.999 if chk.get("pct_limit") else 1.0])
                risk, n = risk * cut, n * cut
            cost = option_side_cost_pct(n, len(DV.legs_from_text(spec["legs"])), prod, account)
            append({**base, "risk_pct": round(risk, 4), "cost_pct": round(cost, 5), "option": spec,
                    "valuation": DV.MODEL_LABEL, "premium_private": True,
                    "capacity": {"pct_adv": round(chk["pct_adv"], 1) if chk.get("pct_adv") is not None else None,
                                 "adv_status": chk.get("adv_status"),
                                 "pct_limit": round(chk["pct_limit"]) if chk.get("pct_limit") is not None else None,
                                 "position_limit": chk.get("position_limit"), "flags": chk["flags"]},
                    "capacity_note": note})
            log.append(f"{pid} filled {spec['structure']} on {o['contract']['code']} ({d}), {risk:.2f}% at risk (model)")
        else:
            s = sign(o["direction"])
            sr = s * (o["stop"] - F) / F
            if sr >= 0:
                append({"type": "cancel", "position_id": pid, "date": d.isoformat(),
                        "reason": "the entry settlement was already through the stop; not opened"})
                return log + [f"{pid} cancelled: entry settlement through the stop"]
            risk = o["risk_pct"]
            nf = (risk / 100.0) / abs(sr)
            cap = CAP.max_notional(o["instrument"], ref, F)
            note = ""
            if cap is not None and nf * account > cap:
                risk = risk * cap / (nf * account)
                nf = cap / account
                note = f"size cut from {o['risk_pct']:.2f}% to {risk:.2f}% at risk to pass the capacity checks"
            chk = CAP.check(o["instrument"], 100 * nf, account, ref, o.get("ann_vol_pct"), 100 * nf, F)
            impact = (chk["impact_bp_trade"] or 0.0) / 1e4
            append({**base, "risk_pct": round(risk, 4),
                    "cost_pct": round(100 * nf * (one_way_cost(prod, F) + impact), 5),
                    "capacity": {"pct_adv": round(chk["pct_adv"], 1) if chk.get("pct_adv") is not None else None,
                                 "adv_status": chk.get("adv_status"),
                                 "pct_limit": round(chk["pct_limit"]) if chk.get("pct_limit") is not None else None,
                                 "position_limit": chk.get("position_limit"), "flags": chk["flags"]},
                    "capacity_note": note, "roll_rule": roll_rule_text(prod)})
            log.append(f"{pid} filled {o['direction']} {o['contract']['code']} ({d}), {risk:.2f}% at risk")
        return log      # the caller rebuilds the position and calls again for the open state
    if p["status"] != "open":
        return log
    f = p["fill"]
    ed = date.fromisoformat(f["entry_date"])
    s = sign(o["direction"])
    hz = date.fromisoformat(o["horizon"])
    cr = date.fromisoformat(p["close_request"]["date"]) if p.get("close_request") else None
    pnl_out.append({"date": ed.isoformat(), "position_id": pid, "gross_pct": "0", "costs_pct": f"{f['cost_pct']:g}",
                    "net_pct": f"{-f['cost_pct']:g}", "basis": "entry", "contract": f["contract"]["code"],
                    "proxy": "yes" if f.get("proxy") else "no"})
    if is_opt:
        spec = f["option"]
        expiry = date.fromisoformat(spec["expiry"])
        up = option_delta_up(spec, exact(rows, prod, f["contract"]["month"], ed) or 1.0, ed)
        days = [x for x in ST.series(rows, prod, f["contract"]["month"]) if ed < x[0] <= today]
        for d, F, _r in days:
            g, basis = gross_pct(p, rows, prod, d)
            if g is None:
                continue
            cost = f["cost_pct"]
            pnl_out.append({"date": d.isoformat(), "position_id": pid, "gross_pct": f"{g:g}", "costs_pct": f"{cost:g}",
                            "net_pct": f"{g - cost:g}", "basis": basis, "contract": f["contract"]["code"],
                            "proxy": "yes" if f.get("proxy") else "no"})
            reason = ("stop" if ((up and F <= p["stop"]) or (not up and F >= p["stop"])) else
                      "option expiry" if d >= expiry else "Janus close decision" if cr and d >= cr else
                      "horizon" if d >= hz else None)
            if reason:
                v0, rpu = option_entry(p, rows, prod)
                n = option_contracts(f["risk_pct"], rpu, prod, account)
                exit_cost = 0.0 if reason == "option expiry" else option_side_cost_pct(n, len(DV.legs_from_text(spec["legs"])), prod, account)
                net = round(g - cost - exit_cost, 4)
                append({"type": "close", "position_id": pid, "date": d.isoformat(), "reason": reason, "basis": basis,
                        "exit_private": True, "exit_digest": digest(f["contract"]["code"], d, F),
                        "mark_source": f["mark_source"], "gross_pnl_pct": g, "exit_cost_pct": round(exit_cost, 5),
                        "net_pnl_pct": net, "outcome": "right" if g > 0 else "wrong", "days_held": (d - ed).days})
                log.append(f"{pid} closed ({reason}) on {d}: gross {g:+.3f}%, net {net:+.3f}%")
                break
        return log
    # futures: rolls first (cost only; the legs carry the P&L), then stop / close request / horizon
    nf = notional_frac(p, rows, prod)
    if nf is None:
        return log + [f"{pid}: entry settlement not in the private store; not marked"]
    held = (p["rolls"][-1]["to_contract"] if p["rolls"] else f["contract"])
    dates = sorted({x[0] for x in ST.series(rows, prod, held["month"]) if ed < x[0] <= today})
    for d in dates:
        if d >= date.fromisoformat(held["notice"]) - timedelta(days=ROLL_BEFORE_NOTICE_DAYS):
            nxt = front(prod, d)
            p_old, p_new = exact(rows, prod, held["month"], d), exact(rows, prod, nxt["month"], d)
            if p_old is None or p_new is None or nxt["month"] == held["month"]:
                continue
            impact = 0.0
            rec = append({"type": "roll", "position_id": pid, "date": d.isoformat(), "from_contract": held,
                          "to_contract": nxt, "private": True,
                          "cost_pct": round(100 * nf * 2.0 * (one_way_cost(prod, p_old) + impact), 5)})
            p["rolls"].append(rec)
            log.append(f"{pid} rolled {held['code']} -> {nxt['code']} on {d}")
            held = nxt
    all_days = sorted({x[0] for leg in legs_of(p) for x in ST.series(rows, prod, leg["month"]) if ed < x[0] <= today})
    for d in all_days:
        rets, cur, _ps = leg_returns(p, rows, prod, d)
        if exact(rows, prod, cur["month"], d) is None:
            continue
        g = round(100 * nf * sum(rets), 4)
        costs = f["cost_pct"] + sum(r.get("cost_pct", 0.0) for r in p["rolls"] if date.fromisoformat(r["date"]) <= d)
        pnl_out.append({"date": d.isoformat(), "position_id": pid, "gross_pct": f"{g:g}", "costs_pct": f"{costs:g}",
                        "net_pct": f"{g - costs:g}", "basis": "settlement", "contract": ST.contract_code(prod, cur["month"]),
                        "proxy": "yes" if f.get("proxy") else "no"})
        thr = threshold(p, rows, prod, d)
        reason = ("stop" if thr is not None and sum(rets) <= thr + 1e-12 else
                  "Janus close decision" if cr and d >= cr else "horizon" if d >= hz else None)
        if reason:
            px = exact(rows, prod, cur["month"], d)
            exit_cost = 100 * nf * one_way_cost(prod, px)
            net = round(g - costs - exit_cost, 4)
            append({"type": "close", "position_id": pid, "date": d.isoformat(), "reason": reason, "basis": "settlement",
                    "contract": contract(prod, cur["month"]), "exit_private": True,
                    "exit_digest": digest(ST.contract_code(prod, cur["month"]), d, px), "mark_source": f["mark_source"],
                    "gross_pnl_pct": g, "exit_cost_pct": round(exit_cost, 5), "net_pnl_pct": net,
                    "outcome": "right" if g > 0 else "wrong", "days_held": (d - ed).days})
            log.append(f"{pid} closed ({reason}) on {d}: gross {g:+.3f}%, net {net:+.3f}%")
            break
    return log
