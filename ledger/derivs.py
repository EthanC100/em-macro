"""Futures by contract month and options (calls, puts, verticals) in the Me book.

    python -m ledger.derivs mark                       # fetch final settlements from Databento (private store,
                                                       # ledger/settlements.py), mark every open futures/option
                                                       # decision, close on stop / horizon / expiry, write P&L in %
                                                       # only to data/ledger/derivative_pnl.csv
    python -m ledger.derivs settle --product BRENT --month 2027-03 --date 2026-11-06 --price 94.00 \\
           --source "..."                                          # enter one settlement by hand (private store)
    python -m ledger.derivs iv D003 48.5 --source "..."            # a new implied vol, only from a stated source
                                                                   # (run through scripts/ledger_commit.sh)
    python -m ledger.derivs value D003 --underlying 100 --date 2026-12-01   # model value at a level (no write)

**Marks.** A futures position is marked at the exchange's final daily settlement of its own contract month, from
Databento GLBX.MDP3 (ledger/settlements.py; the CME website fetch was dropped on 2026-11-06 because cmegroup.com
blocks scripted requests). ICE Brent is marked at the NYMEX Brent Last Day Financial future (BZ) of the same
contract month, which settles to ICE Brent, and every such mark is flagged as a proxy. Spot prices (EIA via FRED) are never used for a contract month: in Nov 2026 spot
Brent was about 107 and March 2027 about 94.

**Licence (docs/ledger/derivatives.md).** CME settlement prices may not be redistributed or republished without
CME's licence, and Databento passes those terms on. So
settlements are stored only in the private repository em-macro-data (``ledger/futures_settlements.csv``, located by
``EM_MACRO_DATA`` or ``../em-macro-data``). This public repository publishes only P&L in % of account
(data/ledger/derivative_pnl.csv), never a settlement, a model value or an exit price. Prices a decision record
states itself (entry level, premium, strikes) are mine and stay in the record.

**Options** are marked to model: Black-76 on the underlying future's daily settlement, with the implied volatility
recorded at entry. It changes only through ``iv`` with a stated source (data/ledger/iv_updates.csv, sealed). The
rate is the 3-month T-bill at entry. The app labels the value a **model estimate**. From the option expiry date
the value is intrinsic: max(F - K, 0) for a call, max(K - F, 0) for a put, on the expiry-day settlement.

**Risk.** For a long call, put or debit vertical the maximum loss is the premium: size (% of account at risk) =
premium x quantity. For a credit vertical it is width - credit. A naked short option has no defined maximum loss
and is rejected. For a future it is |entry - stop| as for any linear position. P&L in % = size x (value - entry
value) / risk per unit.

**Closes.** Only a daily exchange settlement of the contract month (or its flagged proxy), fetched or entered by
hand from a stated exchange source, can act. When it
crosses the stop (a level of the underlying future), the decision closes at that day's model value. It also closes
at the horizon (at the model value) or at the option expiry (at intrinsic value). Monthly, stale or hand-carried
settlements never act.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .schema import parse_date, parse_number, stop_level

ROOT = Path(__file__).resolve().parents[1]
TERMS = "data/ledger/derivatives.csv"
IV_UPDATES = "data/ledger/iv_updates.csv"
PNL = "data/ledger/derivative_pnl.csv"
TERMS_COLUMNS = ["id", "structure", "product", "contract_month", "exchange", "mark_source", "proxy", "legs",
                 "option_expiry", "multiplier", "quantity", "entry_date", "entry_underlying", "entry_premium",
                 "risk_per_unit", "iv_entry_pct", "iv_source", "rate_pct", "logged_at"]
IV_COLUMNS = ["id", "decision", "date", "iv_pct", "source", "logged_at"]
PNL_COLUMNS = ["date", "id", "pnl_pct", "basis", "mark_date", "mark_source", "proxy", "can_act", "note"]
SETTLE_COLUMNS = ["date", "product", "contract_month", "settle", "source", "source_url", "fetched_at", "note"]
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                      "dec"], 1)}
MONTH_CODES = dict(zip("FGHJKMNQUVXZ", range(1, 13)))
STRUCTURES = ("future", "call", "put", "call spread", "put spread")
MODEL_LABEL = "model estimate"

# product -> exchange contract and its mark source (ledger/settlements.py CONTRACTS: Databento final settlements)
from . import settlements as ST  # noqa: E402

ALIASES = {"BRENT": ["ICE Brent", "Brent crude", "Brent"], "WTI": ["NYMEX WTI", "WTI crude", "WTI", "NYMEX crude"],
           "NATGAS": ["Henry Hub", "natural gas", "natgas"], "HEATOIL": ["heating oil", "ULSD"],
           "RBOB": ["RBOB", "gasoline"], "GOLD": ["COMEX gold", "gold"], "SILVER": ["COMEX silver", "silver"],
           "COPPER": ["COMEX copper", "copper"], "CORN": ["CBOT corn", "corn"], "SOYBEANS": ["soybeans", "soybean"],
           "WHEAT": ["CBOT wheat", "SRW wheat", "wheat"]}
PRODUCTS = {
    code: {"name": c.get("proxy_for") or c["name"], "exchange": "ICE" if c.get("proxy") else c["exchange"],
           "aliases": ALIASES[code], "root": c["root"],
           "mark_name": f"{ST.SOURCE} of {c['exchange']} {c['root']}", "proxy": bool(c.get("proxy")),
           "multiplier": c["multiplier"], "unit": c["unit"]}
    for code, c in ST.CONTRACTS.items()}

# extra DECISION RECORD lines for a futures or options position (pasted blocks / the clerk)
FIELDS = {"Structure": "structure", "Contract": "contract", "Legs": "legs", "Option expiry": "option_expiry",
          "Underlying at entry": "entry_underlying", "Premium": "premium", "Implied volatility": "iv",
          "IV source": "iv_source", "Quantity": "quantity"}


# ----------------------------------------------------------------------------- pricing (Black-76)
def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black76(kind: str, F: float, K: float, T: float, sigma: float, r: float = 0.0) -> float:
    """Black-76 price of a European call or put on a future: e^{-rT}[F N(d1) - K N(d2)] (call),
    e^{-rT}[K N(-d2) - F N(-d1)] (put). T in years, sigma and r as fractions. At T <= 0 or sigma <= 0, the
    (discounted) intrinsic value."""
    kind = kind.lower()[0]
    if T <= 0 or sigma <= 0:
        intrinsic = max(F - K, 0.0) if kind == "c" else max(K - F, 0.0)
        return intrinsic * (math.exp(-r * T) if T > 0 else 1.0)
    sd = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sd * sd) / sd
    d2 = d1 - sd
    df = math.exp(-r * T)
    if kind == "c":
        return df * (F * _ncdf(d1) - K * _ncdf(d2))
    return df * (K * _ncdf(-d2) - F * _ncdf(-d1))


def intrinsic(kind: str, F: float, K: float) -> float:
    return max(F - K, 0.0) if kind.lower()[0] == "c" else max(K - F, 0.0)


def structure_value(legs: list[dict], F: float, T: float, sigma: float, r: float = 0.0) -> float:
    """Value per unit of a set of option legs [{'q': +1/-1, 'kind': 'call'/'put', 'strike': K}], or of a future
    (a leg of kind 'future' has value q x F)."""
    v = 0.0
    for leg in legs:
        if leg["kind"] == "future":
            v += leg["q"] * F
        else:
            v += leg["q"] * black76(leg["kind"], F, leg["strike"], T, sigma, r)
    return v


def implied_vol(legs: list[dict], F: float, T: float, price: float, r: float = 0.0,
                lo: float = 0.01, hi: float = 5.0) -> float | None:
    """The lowest volatility at which the structure is worth ``price``. A vertical's value is not monotonic in
    volatility (it goes to 0 as vol grows without bound), so the grid is scanned upward from ``lo`` to the first
    sign change, which is then bisected; None when no volatility up to ``hi`` reproduces the price."""
    f = lambda s: structure_value(legs, F, T, s, r) - price
    grid = [lo + i * 0.01 for i in range(int((hi - lo) / 0.01) + 1)]
    prev = grid[0]
    fp = f(prev)
    for s in grid[1:]:
        fs = f(s)
        if fp == 0:
            return prev
        if (fp < 0) != (fs < 0):
            a, b, fa = prev, s, fp
            for _ in range(100):
                m = 0.5 * (a + b)
                fm = f(m)
                if (fm < 0) == (fa < 0):
                    a, fa = m, fm
                else:
                    b = m
            return 0.5 * (a + b)
        prev, fp = s, fs
    return None


# ----------------------------------------------------------------------------- terms
def parse_month(text: str) -> str | None:
    """'March 2027', 'Mar 27', 'Mar-2027', 'H27', '2027-03' -> '2027-03'."""
    t = (text or "").strip()
    m = re.search(r"\b(20\d\d)-(0[1-9]|1[0-2])\b", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?[\s-]*'?(20\d\d|\d\d)\b", t, re.I)
    if m:
        y = int(m.group(2))
        return f"{y + 2000 if y < 100 else y}-{MONTHS[m.group(1).lower()]:02d}"
    m = re.search(r"\b[A-Z]{1,3}?([FGHJKMNQUVXZ])(\d\d)\b", t)
    if m:
        return f"{2000 + int(m.group(2))}-{MONTH_CODES[m.group(1)]:02d}"
    return None


def match_product(text: str) -> str | None:
    best, n = None, 0
    for code, p in PRODUCTS.items():
        for a in p["aliases"]:
            if re.search(r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z])", text or "", re.I) and len(a) > n:
                best, n = code, len(a)
    return best


_LEG = re.compile(r"(?P<side>long|short|buy|sell|bought|sold|\+\s*\d*|-\s*\d*)\s*(?:(?P<k1>\$?\d+(?:\.\d+)?)\s*"
                  r"(?P<t1>calls?|puts?|c|p)\b|(?P<t2>calls?|puts?)\s*(?:at\s*)?(?P<k2>\$?\d+(?:\.\d+)?))", re.I)


def parse_legs(text: str) -> list[dict]:
    """'long $110 call / short $130 call', '+1 C 110, -1 C 130' (sign, then type and strike), 'long call 110'."""
    legs = []
    t = re.sub(r"([+-]\s*\d*)\s*([CP])\s+(\d+(?:\.\d+)?)", r"\1 \3 \2", text or "", flags=re.I)   # +1 C 110 -> +1 110 C
    for m in _LEG.finditer(t):
        side = m.group("side").lower().replace(" ", "")
        if side in ("long", "buy", "bought"):
            q = 1
        elif side in ("short", "sell", "sold"):
            q = -1
        else:
            q = (-1 if side.startswith("-") else 1) * int(side[1:] or 1)
        k = float((m.group("k1") or m.group("k2")).lstrip("$"))
        kind = "call" if (m.group("t1") or m.group("t2")).lower().startswith("c") else "put"
        legs.append({"q": q, "kind": kind, "strike": k})
    return legs


def legs_text(legs: list[dict]) -> str:
    return "|".join(f"{l['q']:+d} {l['kind']} {l['strike']:g}" if l["kind"] != "future" else f"{l['q']:+d} future"
                    for l in legs)


def legs_from_text(s: str) -> list[dict]:
    out = []
    for part in (s or "").split("|"):
        bits = part.split()
        if len(bits) == 2 and bits[1] == "future":
            out.append({"q": int(bits[0]), "kind": "future", "strike": None})
        elif len(bits) == 3:
            out.append({"q": int(bits[0]), "kind": bits[1], "strike": float(bits[2])})
    return out


def classify(legs: list[dict]) -> str:
    if not legs or all(l["kind"] == "future" for l in legs):
        return "future"
    kinds = {l["kind"] for l in legs}
    if len(legs) == 1:
        return legs[0]["kind"]
    if len(legs) == 2 and len(kinds) == 1 and legs[0]["q"] == -legs[1]["q"]:
        return f"{kinds.pop()} spread"
    return "other"


def risk_per_unit(legs: list[dict], premium: float | None, entry: float | None, stop: float | None) -> tuple[float | None, str | None]:
    """(maximum loss per unit, error). Long premium: the premium. Credit vertical: width - credit. Future: |entry - stop|."""
    st = classify(legs)
    if st == "future":
        if entry is None or stop is None or entry == stop:
            return None, "A futures position needs an entry level and a stop level that differ."
        return abs(entry - stop), None
    if premium is None:
        return None, "An option position needs its premium (net debit, or a negative net credit) per unit."
    if st in ("call", "put"):
        if legs[0]["q"] < 0:
            return None, "A naked short option has no defined maximum loss; the Ledger does not take it."
        if premium <= 0:
            return None, "A long option's premium must be positive."
        return premium * legs[0]["q"], None
    if st.endswith("spread"):
        width = abs(legs[0]["strike"] - legs[1]["strike"]) * abs(legs[0]["q"])
        if width <= 0:
            return None, "A vertical spread needs two different strikes."
        if premium > 0:                                       # debit spread: max loss is the premium
            if premium >= width:
                return None, f"A debit spread's premium ({premium:g}) must be below its width ({width:g})."
            return premium, None
        credit = -premium
        if credit <= 0 or credit >= width:
            return None, f"A credit spread's credit ({credit:g}) must be between 0 and its width ({width:g})."
        return width - credit, None
    return None, "Only futures, single calls or puts and vertical spreads (two legs, same type, opposite sides) are supported."


def is_derivative(fields: dict, instrument: str) -> bool:
    if any((fields.get(k) or "").strip() for k in FIELDS):
        return True
    t = instrument or ""
    return bool(match_product(t) and (parse_month(t) or re.search(r"\b(call|put)s?\b", t, re.I)))


def year_frac(d0: date, d1: date) -> float:
    return max((d1 - d0).days, 0) / 365.0


def parse_iv(text: str) -> tuple[float | None, str]:
    """('Implied volatility: 47.5% (source)' -> 47.5, 'source'); 'implied from premium' -> (None, 'implied')."""
    t = (text or "").strip()
    if re.search(r"implied from (the )?(entry )?premium|back(ed)? out|from the premium", t, re.I) and parse_number(t) is None:
        return None, "implied"
    v = parse_number(t)
    rest = re.sub(r"^\s*[-+]?\d+(?:[.,]\d+)?\s*%?\s*", "", t).strip(" ()-,;:")
    return v, rest


def cash_rate(root: Path, on: date) -> float:
    """3-month T-bill (USDCASH, FRED DTB3) on or before ``on``, in %; 4.0 if none."""
    best = None
    p = root / "data/ledger/marks.csv"
    if p.exists():
        for r in csv.DictReader(p.open(newline="", encoding="utf-8")):
            d = parse_date(r.get("date"))
            if r.get("instrument") == "USDCASH" and r.get("value") and d and d <= on and (best is None or d >= best[0]):
                best = (d, float(r["value"]))
    return best[1] if best else 4.0


def build_terms(fields: dict, rec: dict, root: Path, today: date) -> tuple[dict | None, list[str], list[str]]:
    """(terms row, errors, notes) for a decision that is a futures or options position; (None, [], []) otherwise."""
    get = lambda k: " ".join((fields.get(k) or "").split())
    if not is_derivative(fields, rec.get("instrument", "")):
        return None, [], []
    errors, notes = [], []
    contract = get("Contract") or rec.get("instrument", "")
    product = match_product(contract) or match_product(rec.get("instrument", ""))
    month = parse_month(contract) or parse_month(rec.get("instrument", ""))
    if not product:
        errors.append(f"Futures/options: no supported futures contract named ({', '.join(p['name'] for p in PRODUCTS.values())}); "
                      "add a 'Contract:' line, e.g. 'Contract: ICE Brent March 2027'.")
    if not month:
        errors.append("Futures/options: no contract month found; add e.g. 'Contract: ICE Brent March 2027'.")
    legs = parse_legs(get("Legs")) or parse_legs(rec.get("instrument", ""))
    structure = (get("Structure") or "").lower()
    if not legs and (structure in ("", "future", "futures") and not re.search(r"\b(call|put)s?\b", rec.get("instrument", ""), re.I)):
        legs = [{"q": 1, "kind": "future", "strike": None}]
    elif not legs:
        errors.append("Options: no legs found; add e.g. 'Legs: long 110 call, short 130 call'.")
    if rec.get("action") == "Sell":
        legs = [{**l, "q": -l["q"]} for l in legs]
    st = classify(legs) if legs else "other"
    if structure and legs and not structure.replace("vertical", "spread").replace("futures", "future").startswith(st.split()[0]):
        errors.append(f"Structure says '{structure}' but the legs make a {st}.")
    entry_date = parse_date(rec.get("date")) or today
    F0 = parse_number(get("Underlying at entry"))
    stop = stop_level(rec.get("stop"))
    premium = parse_number(get("Premium"))
    expiry = parse_date(get("Option expiry")) if get("Option expiry") else None
    iv_pct, iv_src = parse_iv(get("Implied volatility"))
    iv_src = get("IV source") or iv_src
    r_pct = cash_rate(root, entry_date)
    if st == "future":
        if F0 is None:
            from .intake import _entry_level_from_trigger
            F0 = parse_number(rec.get("entry_level") or _entry_level_from_trigger(rec.get("entry_trigger", ""), rec))
        if F0 is None:
            errors.append("Futures: the entry level is needed ('Underlying at entry: 94.00' or 'at 94.00' in the trigger).")
    else:
        if F0 is None:
            errors.append("Options: 'Underlying at entry:' (the future's price at entry) is required.")
        if expiry is None:
            errors.append("Options: 'Option expiry:' (a date) is required.")
        elif expiry <= entry_date:
            errors.append("Options: the option expiry must be after the entry date.")
        if premium is None:
            errors.append("Options: 'Premium:' (per unit, e.g. 3.00 per barrel) is required.")
        if iv_pct is None and iv_src != "implied":
            errors.append("Options: 'Implied volatility:' is required: a number with its source (e.g. '48% (CME CVOL, "
                          "6 Nov 2026)') or 'estimate', or 'implied from premium'.")
        elif iv_pct is not None and not (1 <= iv_pct <= 300):
            errors.append("Options: the implied volatility must be in % a year (1 to 300).")
        elif iv_pct is not None and not iv_src:
            errors.append("Options: state the implied volatility's source, or write 'estimate'.")
    risk, err = risk_per_unit(legs, premium, F0, stop) if legs and not errors else (None, None)
    if err:
        errors.append(err)
    if st != "future" and F0 is not None and stop is not None and legs and not errors:
        T = year_frac(entry_date, expiry)
        delta_up = structure_value(legs, F0 * 1.01, T, (iv_pct or 40) / 100, r_pct / 100) - structure_value(legs, F0, T, (iv_pct or 40) / 100, r_pct / 100)
        if (delta_up > 0 and stop >= F0) or (delta_up < 0 and stop <= F0):
            errors.append(f"The stop level {stop:g} (a level of the underlying future) is on the winning side of the "
                          f"entry {F0:g} for this {st}.")
    if errors:
        return None, errors, notes
    if st != "future":
        T = year_frac(entry_date, expiry)
        if iv_src == "implied":
            iv = implied_vol(legs, F0, T, premium, r_pct / 100)
            if iv is None:
                return None, [f"No volatility reproduces the premium {premium:g} for this {st} at {F0:g}."], notes
            iv_pct = round(iv * 100, 2)
            iv_src = (f"estimate: implied from the stated entry premium {premium:g} with Black-76 (F {F0:g}, "
                      f"T {T:.4f}y to {expiry.isoformat()}, r {r_pct:g}%); not an observed market implied volatility")
        model = structure_value(legs, F0, T, iv_pct / 100, r_pct / 100)
        width = abs(legs[0]["strike"] - legs[-1]["strike"]) if st.endswith("spread") else None
        notes.append(f"Black-76 value at entry {model:.2f} against the premium {premium:g} (implied vol {iv_pct:g}%, "
                     f"{iv_src}).")
        if abs(model - premium) > max(0.05 * abs(premium), 0.05):
            notes.append("The model value at entry differs from the premium by more than 5%: the first mark will show "
                         "that difference as P&L.")
        if width:
            notes.append(f"Maximum loss {risk:g} per unit (the premium); maximum value {width:g} at expiry.")
    p = PRODUCTS.get(product, {})
    qty = parse_number(get("Quantity"))
    terms = {"id": "", "structure": st, "product": product, "contract_month": month, "exchange": p.get("exchange", ""),
             "mark_source": p.get("mark_name", ""), "proxy": "yes" if p.get("proxy") else "no", "legs": legs_text(legs),
             "option_expiry": expiry.isoformat() if expiry else "", "multiplier": str(p.get("multiplier", "")),
             "quantity": f"{qty:g}" if qty is not None else "", "entry_date": entry_date.isoformat(),
             "entry_underlying": f"{F0:g}", "entry_premium": f"{premium:g}" if premium is not None and st != "future" else "",
             "risk_per_unit": f"{risk:g}", "iv_entry_pct": f"{iv_pct:g}" if iv_pct is not None and st != "future" else "",
             "iv_source": iv_src if st != "future" else "", "rate_pct": f"{r_pct:g}", "logged_at": today.isoformat()}
    if p.get("proxy"):
        notes.append(f"Marked at the {p['mark_name']} of {month}, a proxy for {p['name']} (flagged as proxy).")
    notes.append("Settlements are licensed (CME terms): they are stored only in em-macro-data; this repository "
                 "publishes P&L in % only" + (", labelled 'model estimate'" if st != "future" else "") + ".")
    return terms, errors, notes


# ----------------------------------------------------------------------------- files
def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _write(path: Path, rows: list[dict], cols: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") or "" for c in cols})


def load_terms(root: Path = ROOT) -> dict[str, dict]:
    return {r["id"]: r for r in _rows(root / TERMS)}


def append_terms(terms: dict, root: Path) -> None:
    rows = _rows(root / TERMS)
    rows.append(terms)
    _write(root / TERMS, rows, TERMS_COLUMNS)


def data_store(root: Path = ROOT) -> Path | None:
    """The private em-macro-data checkout, or None."""
    return ST.store_dir(root)


def settlements(store: Path | None) -> list[dict]:
    return ST.read(store)


def write_settlements(store: Path, new: list[dict]) -> int:
    return ST.write(store, new)


def iv_on(decision: str, d: date, terms: dict, root: Path) -> tuple[float, str]:
    best = (float(terms["iv_entry_pct"]), terms["iv_source"], parse_date(terms["entry_date"]))
    for r in _rows(root / IV_UPDATES):
        rd = parse_date(r.get("date"))
        if r.get("decision") == decision and rd and rd <= d and rd >= best[2]:
            best = (float(r["iv_pct"]), r["source"], rd)
    return best[0], best[1]


def add_iv(decision: str, iv_pct: float, source: str, d: date, root: Path = ROOT, today: date | None = None) -> dict:
    """A new implied volatility for an option decision, only from a stated source."""
    t = load_terms(root).get(decision)
    if not t or t["structure"] == "future":
        raise ValueError(f"{decision} is not an option position")
    if not (source or "").strip() or source.strip().lower() in ("estimate", "guess", "n/a"):
        raise ValueError("an implied volatility update needs a stated source (where the number comes from)")
    if not (1 <= iv_pct <= 300):
        raise ValueError("implied volatility in % a year, 1 to 300")
    rows = _rows(root / IV_UPDATES)
    n = max([int(r["id"][1:]) for r in rows if r.get("id", "")[1:].isdigit()] + [0]) + 1
    rec = {"id": f"V{n:03d}", "decision": decision, "date": d.isoformat(), "iv_pct": f"{iv_pct:g}",
           "source": " ".join(source.split()), "logged_at": (today or date.today()).isoformat()}
    rows.append(rec)
    _write(root / IV_UPDATES, rows, IV_COLUMNS)
    return rec


# ----------------------------------------------------------------------------- valuation
def value(terms: dict, F: float, d: date, root: Path = ROOT, settle_on_expiry: float | None = None) -> tuple[float, str]:
    """(value per unit, basis): 'settlement' for a future, 'model estimate' before an option's expiry,
    'intrinsic at expiry' from its expiry date."""
    legs = legs_from_text(terms["legs"])
    if terms["structure"] == "future":
        return structure_value(legs, F, 0, 0), "settlement"
    expiry = parse_date(terms["option_expiry"])
    if d >= expiry:
        Fx = settle_on_expiry if settle_on_expiry is not None else F
        return sum(l["q"] * intrinsic(l["kind"], Fx, l["strike"]) for l in legs), "intrinsic at expiry"
    iv, _ = iv_on(terms["id"], d, terms, root)
    return structure_value(legs, F, year_frac(d, expiry), iv / 100, float(terms["rate_pct"] or 0) / 100), MODEL_LABEL


def entry_value(terms: dict) -> float:
    if terms["structure"] == "future":
        return structure_value(legs_from_text(terms["legs"]), float(terms["entry_underlying"]), 0, 0)
    return float(terms["entry_premium"])


def exit_value(terms: dict, x: float) -> float:
    """Value per unit of an exit stated as a price: the future's level, or the option / spread price."""
    if terms["structure"] == "future":
        return structure_value(legs_from_text(terms["legs"]), x, 0, 0)
    return x


def pnl_pct(terms: dict, size_pct: float, v: float) -> float:
    return round(size_pct * (v - entry_value(terms)) / float(terms["risk_per_unit"]), 4)


# ----------------------------------------------------------------------------- settlements
def settle_series(rows: list[dict], product: str, month: str) -> list[tuple[date, float, dict]]:
    out = [(parse_date(r["date"]), float(r["settle"]), r) for r in rows
           if r.get("product") == product and r.get("contract_month") == month and r.get("settle")]
    return sorted((x for x in out if x[0]), key=lambda x: x[0])


def can_act(row: dict) -> bool:
    """An exchange settlement of the contract month (fetched, or entered by hand from a stated exchange source) acts;
    a row flagged stale or carried forward does not."""
    note = (row.get("note") or "").lower()
    return bool(row.get("settle")) and "stale" not in note and "carried" not in note


# ----------------------------------------------------------------------------- daily mark
def mark(root: Path = ROOT, today: date | None = None, fetch: bool = True, client=None) -> dict:
    """Mark every open futures/options decision: P&L rows (public, % only), closes (decisions.csv)."""
    from .intake import read_rows, write_rows
    from .schema import AUTO_PREFIX, DECISION_COLUMNS
    today = today or date.today()
    terms = load_terms(root)
    decisions = read_rows(root / "data/ledger/decisions.csv")
    open_ids = {d["id"] for d in decisions if d["id"] in terms}
    store = data_store(root)
    log = []
    if store is None:
        log.append("no private store (em-macro-data not checked out; set EM_MACRO_DATA): entry rows only, no settlement marks")
    elif fetch and open_ids:
        status = {d["id"]: (d.get("status") or "open").lower() for d in decisions}
        needs = {(terms[i]["product"], terms[i]["contract_month"]): parse_date(terms[i]["entry_date"])
                 for i in open_ids if status.get(i) == "open"}
        res = ST.fetch(needs, today, store, c=client, purpose="me")
        log += res["log"]
    srows = settlements(store)
    pnl_rows = {(r["id"], r["date"]): r for r in _rows(root / PNL)}
    changed = []
    for d in decisions:
        t = terms.get(d["id"])
        if not t:
            continue
        size = float(parse_number(d.get("size_pct")) or 0)
        ed = parse_date(t["entry_date"])
        if (d["id"], ed.isoformat()) not in pnl_rows:
            pnl_rows[(d["id"], ed.isoformat())] = {"date": ed.isoformat(), "id": d["id"], "pnl_pct": "0", "basis": "entry",
                                                  "mark_date": ed.isoformat(), "mark_source": "decision record (entry)",
                                                  "proxy": t["proxy"], "can_act": "no", "note": "entry at the recorded level and premium"}
        if (d.get("status") or "open").lower() != "open":
            continue
        series = [x for x in settle_series(srows, t["product"], t["contract_month"]) if x[0] >= ed and x[0] <= today]
        expiry = parse_date(t["option_expiry"]) if t["option_expiry"] else None
        horizon = parse_date(d.get("horizon"))
        stop = stop_level(d.get("stop"))
        legs = legs_from_text(t["legs"])
        up = structure_value(legs, float(t["entry_underlying"]) * 1.01, 0.1, 0.4) > structure_value(legs, float(t["entry_underlying"]), 0.1, 0.4)
        closed = None
        for sd, F, row in series:
            if sd == ed:
                continue                      # the entry day: the record's own level and premium
            v, basis = value(t, F, sd, root)
            p = pnl_pct(t, size, v)
            pnl_rows[(d["id"], sd.isoformat())] = {"date": sd.isoformat(), "id": d["id"], "pnl_pct": f"{p:g}", "basis": basis,
                                                  "mark_date": sd.isoformat(), "mark_source": row.get("source", ""),
                                                  "proxy": t["proxy"], "can_act": "yes" if can_act(row) else "no",
                                                  "note": row.get("note", "")}
            if not can_act(row):
                continue
            hit = stop is not None and ((up and F <= stop) or (not up and F >= stop))
            if hit:
                closed = (sd, p, "stop hit", "wrong", basis)
                break
            if expiry and sd >= expiry:
                closed = (sd, p, "option expiry", None, basis)
                break
            if horizon and sd >= horizon:
                closed = (sd, p, "horizon reached", None, basis)
                break
        if closed:
            sd, p, reason, outcome, basis = closed
            outcome = outcome or ("scratched" if abs(p) < 0.01 else ("right" if p > 0 else "wrong"))
            d.update({"status": "resolved", "outcome": outcome, "pnl_pct": f"{p:g}", "resolved_date": today.isoformat(),
                      "exit_price": f"{basis} (settlement-based; prices kept in em-macro-data)",
                      "resolution_note": f"{AUTO_PREFIX} ({reason}) on {today.isoformat()}: {basis} on the "
                                         f"{sd.isoformat()} settlement of {t['product']} {t['contract_month']} "
                                         f"({t['mark_source']}{', proxy' if t['proxy'] == 'yes' else ''}); P&L {p:+g}% of "
                                         "account. A Resolve form with this id overrides this."})
            changed.append(d["id"])
            log.append(f"{d['id']} closed: {reason} ({sd}), {outcome}, P&L {p:+g}%")
    _write(root / PNL, sorted(pnl_rows.values(), key=lambda r: (r["date"], r["id"])), PNL_COLUMNS)
    if changed:
        write_rows(root / "data/ledger/decisions.csv", decisions, DECISION_COLUMNS)
    return {"closed": changed, "log": log}


def live(decision: dict, root: Path = ROOT) -> dict | None:
    """App fields of a futures/options decision: the latest P&L in % (no prices), its basis and date."""
    t = load_terms(root).get(decision.get("id"))
    if not t:
        return None
    rows = sorted((r for r in _rows(root / PNL) if r["id"] == decision["id"]), key=lambda r: r["date"])
    last = rows[-1] if rows else None
    label = (MODEL_LABEL if t["structure"] != "future" else "settlement") if not last else last["basis"]
    return {"derivative": {k: t[k] for k in ("structure", "product", "contract_month", "exchange", "mark_source", "proxy",
                                              "legs", "option_expiry", "entry_premium", "risk_per_unit", "iv_entry_pct",
                                              "iv_source")},
            "mark_instrument": f"{t['product']} {t['contract_month']}", "mark": None, "mark_unit": None,
            "mark_date": last["date"] if last else None, "mark_frequency": "daily",
            "mark_source": t["mark_source"] + (" (proxy)" if t["proxy"] == "yes" else ""), "mark_source_url": None,
            "mark_note": "settlement prices are licensed and kept privately; only P&L in % is published",
            "mark_can_act": bool(last and last["can_act"] == "yes"), "mark_flag": None,
            "valuation": "entry" if last and last["basis"] == "entry" else label,
            "live_pnl_pct": float(last["pnl_pct"]) if last else None, "stop_distance": None,
            "pnl_history": [[r["date"], float(r["pnl_pct"]), r["basis"]] for r in rows]}


def pnl_on(decision_id: str, d: date, root: Path = ROOT) -> float | None:
    best = None
    for r in _rows(root / PNL):
        rd = parse_date(r["date"])
        if r["id"] == decision_id and rd and rd <= d and (best is None or rd >= best[0]):
            best = (rd, float(r["pnl_pct"]))
    return best[1] if best else None


# ----------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mark")
    m.add_argument("--today", default=None)
    m.add_argument("--no-fetch", action="store_true")
    s = sub.add_parser("settle")
    for k in ("--product", "--month", "--date", "--price", "--source"):
        s.add_argument(k, required=True)
    v = sub.add_parser("iv")
    v.add_argument("decision")
    v.add_argument("iv", type=float)
    v.add_argument("--source", required=True)
    v.add_argument("--date", default=None)
    q = sub.add_parser("value")
    q.add_argument("decision")
    q.add_argument("--underlying", type=float, required=True)
    q.add_argument("--date", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "mark":
        res = mark(today=parse_date(a.today) if a.today else None, fetch=not a.no_fetch)
        print("\n".join(res["log"]) or "nothing to mark")
        print(json.dumps({"closed": res["closed"]}))
        return 0
    if a.cmd == "settle":
        store = data_store()
        if store is None:
            print("no private store: check out em-macro-data next to this repository or set EM_MACRO_DATA", file=sys.stderr)
            return 2
        if a.product not in PRODUCTS or not parse_month(a.month) or not parse_date(a.date) or parse_number(a.price) is None:
            print("product, month (YYYY-MM), date and price are required and must parse", file=sys.stderr)
            return 2
        n = write_settlements(store, [{"date": parse_date(a.date).isoformat(), "product": a.product,
                                       "contract_month": parse_month(a.month), "settle": f"{parse_number(a.price):g}",
                                       "source": " ".join(a.source.split()), "source_url": "",
                                       "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                                       "note": "entered by hand"}])
        print(f"{n} settlement(s) written to the private store")
        return 0
    if a.cmd == "iv":
        rec = add_iv(a.decision, a.iv, a.source, parse_date(a.date) if a.date else date.today())
        print(json.dumps(rec))
        return 0
    t = load_terms().get(a.decision)
    if not t:
        print(f"{a.decision}: no futures/options terms", file=sys.stderr)
        return 2
    d = parse_date(a.date) if a.date else date.today()
    val, basis = value(t, a.underlying, d)
    print(json.dumps({"value_per_unit": round(val, 4), "basis": basis, "entry_value": entry_value(t),
                      "risk_per_unit": float(t["risk_per_unit"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
