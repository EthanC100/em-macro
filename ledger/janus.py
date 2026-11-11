"""Janus: an AI discretionary paper book (an experiment in AI judgement; no edge is claimed).

Janus decides in Claude Code sessions (docs/janus/quick_check.md every 30 minutes, as two hourly scheduled tasks at :15
and :45; docs/janus/daily_review.md
after the US close). No Anthropic API call is made from GitHub Actions. The session never edits data/janus/; every
change goes through this CLI, which enforces every rule in code:

    python -m ledger.janus context [--fetch]         # read-only: rules, open positions, marks, last check, due post-mortems
    python -m ledger.janus propose --file P.json [--dry-run]
                                                     # validate a proposal; if it passes EVERY rule, append it (atomic)
    python -m ledger.janus check --positions J001,J002 --result "no change" --model M
                                                     # a quick check that changed nothing: one record
    python -m ledger.janus mark                      # fills at the next official daily mark; stop / horizon / close fills
    python -m ledger.janus verify                    # the hash chain (exit 1 on failure)
    python -m ledger.janus status

Writes go through scripts/janus_commit.sh, which applies the command on a fresh checkout of origin/main, commits and
pushes, and on a rejected push starts again from the new main, so concurrent writers never break the chain.

Proposal (JSON): {"session": "daily_review" | "quick_check", "model": "...", "session_url": "...", "market_summary": "...",
"reviews": [{"id", "action": "hold" | "close" | "tighten_stop", "new_stop", "reasoning"}],
"new_positions": [{"instrument", "direction", "risk_pct", "stop", "horizon", "probability", "thesis" (2-3 sentences),
"change_mind", "sources": [{"title", "url"}], "opposition": {"case_against", "key_risks", "what_proves_it_wrong",
"probability_view_wrong", "sources", "model"}}], "no_trade_reasoning": "...", "sources_read": [...]}
Daily review from C08 (11 Nov 2026): {"session": "daily_review", "model", "session_url", "market_summary",
"time_anchor": {...}, "sources_read": [...], "forecasts": [{"instrument", "p_initial", "p_final", "reasoning",
"opposition": {"case_against", "probability_view_wrong", "model"}}], "data_failure": [...] (only when a mark failed)}

Account: separate paper account of US$500,000,000, reported in % (index 100 at its start). Its results never feed
the algorithm (v1.0/v1.1) and the algorithm never reads data/janus/.

Records (data/janus/records.jsonl) are append-only and hash-chained: each line carries ``seq``, ``prev_hash`` and
``hash`` = SHA-256 of the previous hash and the canonical JSON of the record without ``hash``. Nothing is edited.

Rules (enforced in code; a proposal that breaks any of them is rejected whole and nothing is appended):
  * universe: only instruments with a free public daily mark (``UNIVERSE``; dropped markets in ``DROPPED``);
  * size = % of account at risk to the stop; at most 2% per position, 10% in total, 8 open positions;
  * capacity (ledger/capacity.py): notional at most 10% of the instrument's ADV and below 80% of any exchange
    position limit (the error states the largest size the stop allows);
  * required: instrument, direction, size, stop on the losing side of the current mark, horizon 1 week to 6 months,
    probability, a 2-3 sentence thesis, what would change its mind, at least one source URL, and The Opposition;
    a reason for every review; a daily review reviews every open position and gives no-trade reasoning when it opens
    nothing; a quick check cannot open positions;
  * mandate of 2026-11-09: a daily review must record its web research in ``sources_read`` (rejected otherwise), and
    may leave the account below 3% at risk only with ``below_budget`` {condition, until, reasoning} naming a specific
    event or condition (or, on a weekend or market holiday, ``deferred_ideas`` for the next trading day); every quick
    check record carries the CLI's flags (a failed or missing daily review, risk below budget without a reason);
  * config change C06 (2026-11-10): at least 2 open positions at all times (``below_budget`` lowers risk, never the
    count); fewer only with ``data_failure`` [{instrument, mark, last_mark}] verified against the marks, and only for
    the instruments affected; an event-based ``below_budget`` gives ``event_date`` and ``calendar_url`` (an official
    calendar listed in ``sources_read``) and expires at the end of the next trading day after the event; a rejected
    daily review appends a failed-review record (``status`` "failed", exit 3) and nothing else;
  * config change C07 (2026-11-10): no opened position (or deferred idea) at probability 50; when the C06 minimum
    binds, ``candidates`` lists at least 5 instruments across at least 2 asset classes (rates, FX, commodities), and a
    candidate dropped after The Opposition is reopened only with a ``reopen_reason`` naming why each other candidate
    is not better; ``time_anchor`` {now_utc, events [{event, time_utc or date, occurred}]} covers every date and
    scheduled event named in a reason or thesis, and no event dated in the future is described as released; a
    deferred idea counts toward the minimum only if its market is closed on the review date (weekend, FX on 1 Jan or
    25 Dec, otherwise ``market_closed`` {holiday, calendar_url}) and must open at the next session;
  * config change C08 (approved 2026-11-11, from the 11 Nov 2026 daily review), replacing discretionary position
    selection: a daily review gives ``forecasts``, one per instrument of janus/watchlist.yaml, each with ``p_initial``
    (before The Opposition) and ``p_final``, whole numbers from 1 to 99, never 50 (The Opposition is advisory and
    never vetoes a forecast); every forecast is logged and resolved with a Brier score (``forecast_resolution``,
    by ``mark``). The CLI sets the book: each instrument on the side of its final forecast, risk proportional to
    |p - 50| (0.1% a point, 2% cap) scaled into C05's 3-10% band, rebalanced at each daily review with a 25%
    no-trade band; only a verified ``data_failure`` excludes an instrument. new_positions, reviews, below_budget,
    candidates and deferred_ideas are rejected in a daily review; a quick check cannot close or tighten a C08
    position. The first C08 review closes every earlier position (J001, J002) as its closing action. Kept:
    sources_read, the time anchor, failed-review records (exit 3). Superseded: C05 (b)'s sizing table,
    below_budget and deferrals, C06 rules 1-2, C07 rules 1, 2 and 4;
  * stops can only be tightened; positions close automatically at the first daily mark through the stop, at the
    first mark dated on or after the horizon, or at the first mark dated on or after a close decision;
  * entry at the next official daily mark: the first first-hand daily mark dated on or after the decision's UTC date.
    If that mark is already through the stop the order is cancelled; if it changes the capacity limit, the size is
    cut to fit and the cut is logged with the fill;
  * costs: the algorithm's cost model (10bp of notional per one-way trade for major FX and developed bonds, 20bp
    for a spread, two legs) and, for commodity futures, the T20-T22 model (2 x (US$3 commission + 1 tick) per
    contract per side, a roll counted as two trades), plus the square-root impact estimate on every trade;
  * commodity roll rule (logged with each fill and roll): hold the earliest contract whose notice date is more
    than 35 calendar days after the trade date; roll when the held contract is within 10 calendar days of its notice
    date (calendar approximations, ``NOTICE_RULES``). Commodity P&L is marked on the official spot price (an
    estimate; roll yield is not captured, roll costs are charged).
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import math
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import capacity as CAP
from . import janus_fut as JF
from . import pricing as PX
from . import settlements as ST
from .marks import load_registry, mark_can_act, read_marks
from .schema import parse_date

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data/janus"
RECORDS = DIR / "records.jsonl"
ACCOUNT_USD = CAP.JANUS_CAPITAL
MAX_RISK_POS, MAX_RISK_TOTAL, MAX_OPEN = 2.0, 10.0, 8
# Mandate of 2026-11-09 (docs/janus/daily_review.md; docs/config_changes.md C05), set before any position was opened
MANDATE_FROM = date(2026, 11, 9)
RISK_BUDGET = (3.0, 10.0)            # normal % of the account at risk; below 3% only with a specific, dated reason
TYPICAL_POSITIONS = (2, 6)
SMALL_EDGE_RISK = (0.25, 0.5)        # % at risk for a small edge over the market probability
RESEARCH_DRIVERS = ("central banks", "data", "geopolitics", "positioning")
BELOW_BUDGET_MAX_DAYS = 30           # below_budget.until: when the condition resolves or is reassessed
GENERIC_REASON = re.compile(
    r"\b(no|lack of|without|absence of)\s+(an?\s+|clear\s+|real\s+|defensible\s+|obvious\s+|strong\s+|good\s+)*"
    r"(edge|view|conviction|opportunit\w*|set-?ups?|trades?|ideas?)\b|\bnothing\s+(clears|compelling|stands)|"
    r"^\s*(uncertainty|volatility|markets? (are|is) (uncertain|volatile)|wait and see)\W*$", re.I)
# Config change C06 (approved 2026-11-10, effective from that day's daily review; docs/config_changes.md C06)
C06_FROM = date(2026, 11, 10)
MIN_POSITIONS = TYPICAL_POSITIONS[0]  # hard: below_budget lowers risk, never the position count
DATA_STALE_WEEKDAYS = 2               # a mark is stale when at least this many weekdays have passed without one
# Official calendars an event reason may cite (host or any subdomain of it): statistics offices, central banks,
# treasuries and official bodies. Adding one is a config change.
OFFICIAL_CALENDAR_HOSTS = (
    "bls.gov", "bea.gov", "census.gov", "dol.gov", "federalreserve.gov", "newyorkfed.org", "treasury.gov",
    "treasurydirect.gov", "eia.gov", "usda.gov", "cftc.gov",
    "ecb.europa.eu", "ec.europa.eu", "bundesbank.de", "destatis.de", "insee.fr", "banque-france.fr", "aft.gouv.fr",
    "bankofengland.co.uk", "ons.gov.uk", "dmo.gov.uk",
    "boj.or.jp", "mof.go.jp", "stat.go.jp", "esri.cao.go.jp",
    "snb.ch", "bfs.admin.ch", "rba.gov.au", "abs.gov.au", "bankofcanada.ca", "statcan.gc.ca", "opec.org")
EVENT_REASON = re.compile(
    r"\b(CPI|PCE|PPI|HICP|inflation (data|print|release|report)|payrolls?|NFP|jobs report|employment report|GDP|"
    r"retail sales|PMI|ISM|FOMC|ECB|BoE|BoJ|SNB|RBA|BoC|MPC|central[- ]bank (decision|meeting)|rate decision|"
    r"policy (decision|meeting)|meeting|minutes|release|print|auction|election|vote|referendum|budget|OPEC\+?|"
    r"WASDE|testimony|speech|summit)\b|"
    r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b|"
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b|\b\d{4}-\d{2}-\d{2}\b", re.I)
# C06 expiry of below_budget reasons recorded before C06, by the run record's hash (each with its correction-log id)
BELOW_BUDGET_EXPIRY_CORRECTIONS = {
    # 10 Nov 2026 review (seq 199): dated US CPI to 12 Nov; BLS lists 10 Nov 2026, 08:30 ET (correction K004)
    "c8cab8c4c6e3659de0c9cf8c9c896f304012af03f20f909f43f2751ba979b33d": ("K004", date(2026, 11, 11)),
}
# Config change C07 (approved by Ethan 2026-11-10, effective from the first daily review after it was recorded on
# 2026-11-10; docs/config_changes.md C07): no 50% calls, a wider search when the C06 minimum binds, a time anchor,
# and deferrals that count toward the minimum only where the instrument's market is closed
C07_FROM = date(2026, 11, 10)
NO_VIEW_PROBABILITY = 50.0           # an opened position's probability may not be exactly this (C07 rule 1)
MIN_CANDIDATES, MIN_CANDIDATE_CLASSES = 5, 2   # when the C06 minimum binds (C07 rule 2)
CANDIDATE_CLASS = {"rates": "rates", "rates spread": "rates", "fx": "fx", "future": "commodities"}
CANDIDATE_OUTCOMES = ("opened", "deferred", "not_opened")
OPPOSITION_OUTCOMES = ("kept", "dropped", "none")
ANCHOR_MAX_AGE = timedelta(hours=3)  # time_anchor.now_utc: at most this old when the CLI validates the review
ANCHOR_MAX_AHEAD = timedelta(minutes=5)
# Exchange and market-association calendars a weekday market closure may cite (C07 rule 4), besides the official
# calendars above. Adding one is a config change.
MARKET_CALENDAR_HOSTS = ("cmegroup.com", "sifma.org", "theice.com", "ice.com", "eurex.com", "jpx.co.jp",
                         "londonstockexchange.com")
FX_CLOSED_DAYS = ((1, 1), (12, 25))  # FX trades every weekday except these (C07 rule 4)
MIN_HORIZON_DAYS, MAX_HORIZON_DAYS = 5, 190
# Config change C08 (approved by Ethan 2026-11-11, effective from the 11 November 2026 daily review;
# docs/config_changes.md C08): forced forecasts on a fixed watchlist (janus/watchlist.yaml), every one logged and
# resolved with a Brier score, and a mechanical book set by the CLI, not by Janus. It supersedes discretionary
# position selection: C05 (b)'s sizing table, below_budget and weekend deferrals, C06 rules 1-2, C07 rules 1, 2 and 4.
C08_FROM = date(2026, 11, 11)
WATCHLIST_FILE = ROOT / "janus/watchlist.yaml"
C08_PROBABILITY_RANGE = (1, 99)       # whole numbers; 50 is never a forecast
C08_RISK_PER_POINT = 0.1              # % at risk per point of |p_final - 50|, before scaling into the C05 band
C08_NO_TRADE_BAND = 0.25              # a held position is resized only when its target risk moves more than 25%
C08_DISCRETIONARY = ("new_positions", "reviews", "below_budget", "candidates", "deferred_ideas")
ROLL_BUFFER_DAYS, ROLL_BEFORE_NOTICE_DAYS = 35, 10
MONTH_CODES = "FGHJKMNQUVXZ"
GENESIS = "0" * 64

# instrument -> description; ``cost`` is the one-way cost per unit of notional (the algorithm's model)
UNIVERSE = {
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
    # added by config change C09 (2026-11-11) for the C08 watchlist: EM FX on central-bank fixings; the algorithm's
    # cost model treats both as major currencies (10bp one way)
    "BRL": dict(name="BRL per USD, BCB PTAX (long = long Brazilian real)", asset_class="fx", country="Brazil",
                currency="BRL", cost=0.001),
    "MXN": dict(name="MXN per USD, Banxico FIX (long = long Mexican peso)", asset_class="fx", country="Mexico",
                currency="MXN", cost=0.001),
}
# CME-group futures by contract month (ledger/settlements.py, ledger/janus_fut.py): energy, COMEX metals, CBOT
# grains, marked at Databento final settlements stored privately; options only as defined-risk structures
COUNTRY_OF = {"BRENT": "Global", "GOLD": "Global", "SILVER": "Global", "COPPER": "Global"}
UNIVERSE.update({
    code: dict(name=c["name"] + " by contract month", asset_class="future", sector=c["sector"],
               country=COUNTRY_OF.get(code, "United States"), currency="USD", product=code, contract=c["root"],
               exchange=c["exchange"], multiplier=c["multiplier"], tick_value=c["tick_value"], unit=c["unit"],
               proxy=bool(c.get("proxy")))
    for code, c in ST.CONTRACTS.items()})
DROPPED = [
    {"market": "Italy 10y spread over Germany (IT-DE)",
     "reason": "No free daily source: the ECB publishes country yields monthly only, Banca d'Italia's Infostat needs a "
               "session and the Riksbank publishes no Italian series. Only a monthly average is available, which can "
               "neither enter nor stop a position."},
    {"market": "Platinum, palladium, KC wheat, soybean meal and oil, livestock, softs",
     "reason": "Not added (2026-11-06): the universe is NYMEX energy, COMEX gold, silver and copper, and CBOT corn, "
               "soybeans and Chicago wheat. ICE softs are not on Databento's CME feed."},
    {"market": "Spot-price estimates for energy (EIA via FRED)",
     "reason": "Replaced on 2026-11-06 by futures by contract month marked at final exchange settlements "
               "(Databento GLBX.MDP3, stored privately); spot is never used for a contract month."},
    {"market": "Norgate",
     "reason": "Licence: never used for Janus. (Janus's futures settlements come from Databento and are kept in "
               "em-macro-data, never in this repository.)"},
]
def is_future(inst: str) -> bool:
    return UNIVERSE.get(inst, {}).get("asset_class") == "future"


def front_contract(inst: str, d: date) -> dict:
    """The earliest listed contract whose notice date is more than 35 days after ``d`` (T20-T22's buffer)."""
    c = JF.front(inst, d)
    return {**c, "delivery": c["month"]}


def roll_rule_text(inst: str) -> str:
    return JF.roll_rule_text(inst)


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
    if is_future(inst):
        return JF.one_way_cost(inst, level)
    return UNIVERSE[inst]["cost"]


def size(inst: str, direction: str, risk_pct: float, entry: float, stop: float, reg: dict[str, dict],
         ref: dict[str, dict], vol: float | None = None) -> dict:
    """Notional for ``risk_pct`` at risk to the stop, cut to the capacity limits."""
    k = kind(inst, reg)
    sr = PX.stop_return(k, direction, entry, stop)
    if sr is None or sr >= 0:
        raise ValueError("stop is not on the losing side of the entry")
    notional_frac = (risk_pct / 100.0) / abs(sr)
    notional = notional_frac * ACCOUNT_USD
    price = entry if is_future(inst) else None
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
def settlement_rows() -> list[dict]:
    """Janus's futures marks: the private settlement store (empty when em-macro-data is not checked out)."""
    return ST.read(ST.store_dir())


def pnl_path(path: Path | None) -> Path:
    return (path.parent if path else DIR) / "futures_pnl.csv"


def process(records: list[dict], marks_rows: list[dict], today: date, path: Path | None = RECORDS,
            settle_rows: list[dict] | None = None) -> list[str]:
    """Fill pending orders, roll futures, close on stop / horizon / close request. Returns log lines. Futures and
    options are processed from the private settlements (``settle_rows``, default the store) by ledger/janus_fut.py;
    without them they are left as they are."""
    reg = registry_rows()
    ref = CAP.load_reference()
    log = []
    srows = settle_rows if settle_rows is not None else None
    pnl_out: list[dict] = []
    log += c08_rebalance_fills(records, marks_rows, today, path, reg, ref)    # C08 resizes and flips, at one mark
    for pid, p in sorted(positions(records).items()):
        o = p["open"]
        inst, direction = o["instrument"], o["direction"]
        if is_future(inst):
            if srows is None:
                srows = settlement_rows()
            if not srows:
                if p["status"] in ("pending", "open"):
                    log.append(f"{pid}: no private settlements in this run (em-macro-data); not processed")
                continue
            add = lambda rec: append(records, rec, path)
            was_pending = p["status"] == "pending"
            log += JF.process_position(p, inst, srows, today, ref, ACCOUNT_USD, add, pnl_out)
            p = positions(records)[pid]
            if was_pending and p["status"] == "open":       # filled now: mark, roll and close from the fill on
                log += JF.process_position(p, inst, srows, today, ref, ACCOUNT_USD, add, pnl_out)
            continue
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
            append(records, fill, path)
            log.append(f"{pid} filled {direction} {inst} at {v:g} ({d}); notional US${sz['notional_usd'] / 1e6:,.1f}m")
            p = positions(records)[pid]
        if p["status"] != "open":
            continue
        f = p["fill"]
        ed = parse_date(f["entry_date"])
        after = [x for x in ser if ed < x[0] <= today]
        reason, hit = None, None
        hz = parse_date(o["horizon"])
        cr = parse_date((p.get("close_request") or {}).get("date"))
        for d, v, m in after:
            stop_now = stop_on(p, d)
            if PX.stop_hit(k, direction, f["entry_level"], stop_now, v):
                reason, hit = "stop", (d, v, m)
                break
            if cr and d >= cr:
                reason, hit = (p["close_request"].get("close_reason") or "Janus close decision"), (d, v, m)
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
    if pnl_out and path is not None:
        JF.write_pnl(pnl_path(path), pnl_out)
    log += resolve_forecasts(records, marks_rows, today, path)              # C08: every forecast, Brier scored
    return log


# ----------------------------------------------------------------------------- summary for the app
def summarize(records: list[dict], marks_rows: list[dict], today: date | None = None,
              pnl_rows: list[dict] | None = None) -> dict:
    today = today or date.today()
    reg = registry_rows()
    pnl_rows = pnl_rows if pnl_rows is not None else JF.read_pnl(pnl_path(RECORDS))
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
        row["market_probability"] = o.get("market_probability")
        row["market_source"] = o.get("market_source")
        row["market_basis"] = o.get("market_basis")
        if is_future(inst):
            # futures / options: P&L in % only (settlements are licensed and kept privately)
            row.update({"mark": None, "mark_date": None, "mark_history": [], "unit": UNIVERSE[inst].get("unit"),
                        "contract": (p["rolls"][-1]["to_contract"] if p["rolls"] else (p["fill"] or o).get("contract")),
                        "option": (p["fill"] or o).get("option"), "proxy": UNIVERSE[inst].get("proxy"),
                        "valuation": JF.DV.MODEL_LABEL if o.get("option") else "settlement",
                        "mark_flag": None if p["fill"] else "awaiting the first final settlement on or after the decision date"})
            if p["close"]:
                row.update({"gross_pnl_pct": p["close"]["gross_pnl_pct"], "net_pnl_pct": p["close"]["net_pnl_pct"],
                            "valuation": p["close"].get("basis") or row["valuation"]})
            elif p["fill"]:
                last_p = JF.pnl_on(pnl_rows, pid, today)
                if last_p:
                    row.update({"gross_pnl_pct": float(last_p["gross_pct"]), "net_pnl_pct": float(last_p["net_pct"]),
                                "mark_date": last_p["date"], "valuation": last_p["basis"]})
            rows.append(row)
            if p["close"]:
                closed.append(row)
            continue
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
    eq = equity(records, marks_rows, today, pnl_rows)
    bench = benchmark(records, marks_rows, today, pnl_rows)
    open_rows = [r for r in rows if r["status"] in ("open", "pending")]
    return {
        "start": start, "account_usd": ACCOUNT_USD, "model": next((r["model"] for r in reversed(records) if r.get("model")), None),
        "positions": rows, "open": open_rows, "closed": closed,
        "no_trades": [{"date": r["date"], "reasoning": r["reasoning"], "model": r.get("model"), "decided_at": r.get("decided_at")}
                      for r in records if r["type"] == "no_trade"],
        "runs": [{k: r.get(k) for k in ("session", "date", "decided_at", "model", "market_summary", "n_new", "n_reviews",
                                          "usage", "searches", "status", "session_url")} for r in records if r["type"] == "run"],
        "checks": [{k: r.get(k) for k in ("time", "positions", "result", "model", "session_url")}
                   for r in records if r["type"] == "check"][-20:],
        "last_check": _last_check(records),
        "fill_rule": "Trades fill at the next official daily mark (the first first-hand daily mark dated on or after the "
                     "decision date), not at the price when Janus decides.",
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
                      **({"unit": v["unit"], "source": "Databento GLBX.MDP3 final settlement (private)",
                          "source_id": f"{v['contract']} by contract month", "source_url": "https://databento.com",
                          "notes": ("Settlements are licensed and kept in em-macro-data; only P&L in % is published."
                                    + (" Held and marked as NYMEX BZ, a proxy for ICE Brent." if v.get("proxy") else ""))}
                         if v["asset_class"] == "future" else
                         {"unit": reg.get(k, {}).get("unit"), "source": reg.get(k, {}).get("source"),
                          "source_id": reg.get(k, {}).get("source_id"), "source_url": reg.get(k, {}).get("source_url"),
                          "notes": reg.get(k, {}).get("notes")}),
                      "roll_rule": roll_rule_text(k) if v["asset_class"] == "future" else None}
                     for k, v in UNIVERSE.items()],
        "dropped": DROPPED, "chain": verify(records),
        # config change C08: every forced forecast with its resolution and Brier score, and the fund rule's resolved
        # calls (C09: one call per correlation cluster per non-overlapping 20-trading-day window; allocation.md)
        "forecasts": forecast_rows(records), "forecast_summary": forecast_summary(records),
        "fund_calls": fund_calls(records),
        "disclaimer": ("Janus is an experiment in AI judgement. Its results do not feed the algorithm (v1.0 and v1.1 are "
                       "mechanical rules and never read Janus's records), and no edge is claimed."),
    }


def _last_check(records: list[dict]) -> dict | None:
    """The latest session that looked at the book: a check record, or a run (quick check or daily review)."""
    best = None
    for r in records:
        if r["type"] == "check":
            best = {"time": r["time"], "session": "quick_check", "result": r["result"], "positions": r["positions"]}
            if r.get("flags"):
                best["flags"] = r["flags"]
                best["result"] = f"{r['result']} · FLAG: " + "; ".join(r["flags"])
        elif r["type"] == "run":
            what = (f"{r.get('n_reviews', 0)} review(s), {r.get('n_new', 0)} new position(s)" if r.get("session")
                    else "weekly run (API, before sessions)")
            if r.get("status") == "failed":
                what = "daily review rejected by the CLI (failed-review record); nothing applied"
            best = {"time": r.get("decided_at"), "session": r.get("session") or "weekly run", "result": what,
                    "positions": None}
    return best


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


def equity(records: list[dict], marks_rows: list[dict], today: date, pnl_rows: list[dict] | None = None) -> list[list]:
    """[[date, index]] daily from the account start: 100 + net P&L (% of the starting account), positions marked
    at the latest daily mark on or before each date (carried forward on days without one)."""
    start = account_start(records)
    if not start:
        return []
    reg = registry_rows()
    sd = parse_date(start["date"])
    pos = positions(records)
    sers = {p["open"]["instrument"]: series(marks_rows, p["open"]["instrument"]) for p in pos.values()
            if not is_future(p["open"]["instrument"])}
    pnl_rows = pnl_rows if pnl_rows is not None else JF.read_pnl(pnl_path(RECORDS))
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
            if is_future(p["open"]["instrument"]):
                r = JF.pnl_on(pnl_rows, p["id"], d)
                total += float(r["net_pct"]) if r else -f.get("cost_pct", 0.0)
                continue
            lv = _level_on(sers[p["open"]["instrument"]], d)
            if lv is None:
                continue
            gross = pnl_at(p, lv[1], reg)["gross_pct"]
            costs = f.get("cost_pct", 0.0) + sum(r.get("cost_pct", 0.0) for r in p["rolls"] if parse_date(r["date"]) <= d)
            total += gross - costs
        out.append([d.isoformat(), round(100.0 + total, 4)])
    return out


def benchmark(records: list[dict], marks_rows: list[dict], today: date, pnl_rows: list[dict] | None = None) -> dict:
    """Equal-weight benchmark of the same instruments: each instrument Janus traded, held LONG over the same dates,
    every position at the same notional (the average of Janus's notionals), no costs. Janus minus this isolates the
    value of its direction and sizing choices."""
    reg = registry_rows()
    # futures and options have no public price (licensed settlements), so the benchmark covers the other instruments
    pos = [p for p in positions(records).values() if p["fill"] and not is_future(p["open"]["instrument"])]
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
    eq = equity(records, marks_rows, today, pnl_rows)
    return {"pnl_pct": round(tot, 4), "janus_pnl_pct": round(eq[-1][1] - 100, 4) if eq else None, "n": len(pos),
            "method": "Equal-weight benchmark: the same instruments over the same dates, always long, each at Janus's "
                      "average notional, before costs. Futures and options are left out (their prices are private)."}


# ----------------------------------------------------------------------------- the weekly run
def market_snapshot(marks_rows: list[dict], today: date, settle_rows: list[dict] | None = None) -> list[dict]:
    """The universe with marks, for a session's context only (never published: futures settlements are licensed)."""
    reg = registry_rows()
    out = []
    srows = settle_rows if settle_rows is not None else None
    for inst, u in UNIVERSE.items():
        if is_future(inst):
            srows = settlement_rows() if srows is None else srows
            fc = front_contract(inst, today)
            ser_f = ST.series(srows, inst, fc["month"])
            row = {"instrument": inst, "name": u["name"], "unit": u["unit"], "front_contract": fc["code"],
                   "front_month": fc["month"], "notice": fc["notice"], "proxy": u.get("proxy", False),
                   "private": "settlements are licensed: use them in this session only, never in a public file"}
            if ser_f:
                last = ser_f[-1]
                row.update({"mark": last[1], "mark_date": last[0].isoformat(),
                            "level_1w_ago": (ST.on_or_before(srows, inst, fc["month"], last[0] - timedelta(days=7)) or [None, None])[1]})
            else:
                row.update({"mark": None, "note": "no private settlements in this session (check out em-macro-data)"})
            out.append(row)
            continue
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
        out.append(row)
    return out


THESIS_SENTENCES = (2, 3)
SESSIONS = ("daily_review", "quick_check")


def _sentences(text: str) -> int:
    t = " ".join(str(text or "").split())
    if not t:
        return 0
    return len([m for m in re.finditer(r"[.!?](?=\s+[A-Z(\"'0-9]|\s*$)", t)]) or 1


def _url_ok(u) -> bool:
    return isinstance(u, str) and re.match(r"^https?://\S+\.\S+", u) is not None


def validate(ans: dict, records: list[dict], marks_rows: list[dict], today: date,
             now: datetime | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """Check a proposal against every rule. Returns (reviews, new positions, errors); any error rejects the whole
    proposal (nothing is appended), so the session fixes it and proposes again. ``now`` (UTC) is the CLI's clock,
    against which C07's time anchor is checked (default: now, or the end of ``today`` for a past date)."""
    if now is None:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        if now.date() != today:
            now = datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc).replace(microsecond=0)
    reg = registry_rows()
    ref = CAP.load_reference()
    pos = positions(records)
    errors, reviews, new = [], [], []
    session = ans.get("session")
    if session not in SESSIONS:
        errors.append(f"session must be one of {SESSIONS}, got {session!r}")
    if not str(ans.get("model") or "").strip():
        errors.append("model is required (the model string of the session that decided)")
    open_ids = sorted(pid for pid, p in pos.items() if p["status"] in ("open", "pending"))
    seen = set()
    for r in ans.get("reviews") or []:
        pid = str(r.get("id", "")).strip()
        p = pos.get(pid)
        if not p or p["status"] not in ("open", "pending"):
            errors.append(f"review of {pid!r}: not an open position")
            continue
        if pid in seen:
            errors.append(f"{pid}: reviewed twice")
            continue
        seen.add(pid)
        act = str(r.get("action", "")).lower()
        if act not in ("hold", "close", "tighten_stop"):
            errors.append(f"{pid}: action must be hold, close or tighten_stop (got {act!r})")
            continue
        if p["open"].get("c08"):
            errors.append(f"{pid}: a C08 position is set by the CLI at each daily review; a session cannot close or "
                          "tighten it (C08). A quick check records a check instead")
            continue
        if not str(r.get("reasoning") or "").strip():
            errors.append(f"{pid}: a reason is required for every review")
            continue
        if act == "tighten_stop" and is_future(p["open"]["instrument"]):
            o = p["open"]
            try:
                ns = float(r.get("new_stop"))
            except (TypeError, ValueError):
                errors.append(f"{pid}: tighten_stop needs a numeric new_stop")
                continue
            srows = settlement_rows()
            con = (p["rolls"][-1]["to_contract"] if p["rolls"] else (p["fill"] or o).get("contract"))
            ser = ST.series(srows, o["instrument"], con["month"]) if con else []
            if not ser:
                errors.append(f"{pid}: tightening a futures stop needs the private settlements (em-macro-data)")
                continue
            cur = ser[-1][1]
            up = (JF.option_delta_up(o["option"], cur, today) if o.get("option") else o["direction"] == "long")
            old_s = p["stop"]
            tighter = (ns > old_s) if up else (ns < old_s)
            if not tighter:
                errors.append(f"{pid}: new stop {ns:g} would widen or not move the stop {old_s:g} (stops can only be tightened)")
                continue
            if (up and ns >= cur) or (not up and ns <= cur):
                errors.append(f"{pid}: new stop {ns:g} is already through the latest settlement; propose a close instead")
                continue
            reviews.append({**r, "id": pid, "action": act, "new_stop": ns})
            continue
        if act == "tighten_stop":
            o = p["open"]
            ser = series(marks_rows, o["instrument"], actable_only=False)
            k = kind(o["instrument"], reg)
            try:
                ns = float(r.get("new_stop"))
            except (TypeError, ValueError):
                errors.append(f"{pid}: tighten_stop needs a numeric new_stop")
                continue
            base = p["fill"]["entry_level"] if p["fill"] else (ser[-1][1] if ser else None)
            old_r = PX.stop_return(k, o["direction"], base, p["stop"])
            new_r = PX.stop_return(k, o["direction"], base, ns)
            cur = ser[-1][1] if ser else None
            if new_r is None or old_r is None or new_r <= old_r + 1e-12:
                errors.append(f"{pid}: new stop {ns:g} would widen or not move the stop {p['stop']:g} (stops can only be tightened)")
                continue
            if cur is not None and not PX.valid_stop(k, o["direction"], cur, ns):
                errors.append(f"{pid}: new stop {ns:g} is already through the current mark {cur:g}; propose a close instead")
                continue
            r = {**r, "new_stop": ns}
        reviews.append({**r, "id": pid, "action": act})
    if session == "daily_review":
        missing = [i for i in open_ids if i not in seen]
        if missing:
            errors.append(f"daily review must review every open position with a reason; missing {', '.join(missing)}")
        if not (ans.get("new_positions") or []) and not str(ans.get("no_trade_reasoning") or "").strip():
            errors.append("no new positions: no_trade_reasoning is required")
    if session == "quick_check":
        if ans.get("new_positions"):
            errors.append("a quick check cannot open positions (new positions need the daily review and The Opposition)")
        if not reviews and not errors:
            errors.append("nothing to apply: when nothing changed, record a check (python -m ledger.janus check) instead")
    total = open_risk(pos) - sum(pos[r["id"]]["open"]["risk_pct"] for r in reviews if r["action"] == "close")
    n_open = len(open_ids) - sum(1 for r in reviews if r["action"] == "close")
    for i, n in enumerate(ans.get("new_positions") or [], 1):
        inst = str(n.get("instrument", "")).strip().upper()
        tag = f"new position {i} ({inst or '?'})"
        errs = []
        if inst not in UNIVERSE:
            errors.append(f"{tag}: not in the universe ({', '.join(UNIVERSE)})")
            continue
        direction = str(n.get("direction", "")).lower()
        if direction not in ("long", "short") and not (is_future(inst) and n.get("option")):
            errs.append(f"direction must be long or short, got {direction!r}")
        try:
            risk, stop, prob = float(n.get("risk_pct")), float(n.get("stop")), float(n.get("probability"))
        except (TypeError, ValueError):
            errors.append(f"{tag}: risk_pct, stop and probability must be numbers")
            continue
        hz = parse_date(n.get("horizon"))
        if not hz or not (today + timedelta(days=MIN_HORIZON_DAYS) <= hz <= today + timedelta(days=MAX_HORIZON_DAYS)):
            errs.append(f"horizon {n.get('horizon')!r} must be a date between {MIN_HORIZON_DAYS} days and 6 months ahead")
        if not (0 < prob <= 100):
            errs.append(f"probability {prob:g} must be in (0, 100]")
        ns = _sentences(n.get("thesis"))
        if not (THESIS_SENTENCES[0] <= ns <= THESIS_SENTENCES[1]):
            errs.append(f"thesis must be 2-3 sentences (found {ns})")
        if not str(n.get("change_mind") or "").strip():
            errs.append("change_mind (what would change its mind) is required")
        srcs = [x for x in (n.get("sources") or []) if isinstance(x, dict) and _url_ok(x.get("url"))]
        if not srcs:
            errs.append("at least one source with a URL is required")
        opp = n.get("opposition") or {}
        if not str(opp.get("case_against") or "").strip():
            errs.append("The Opposition is required: opposition.case_against (written by a separate reviewer)")
        if risk <= 0:
            errs.append(f"risk_pct {risk:g} must be positive")
        if risk > MAX_RISK_POS + 1e-9:
            errs.append(f"risk_pct {risk:g}% is above the {MAX_RISK_POS:g}% per-position limit")
        if total + risk > MAX_RISK_TOTAL + 1e-9:
            errs.append(f"risk_pct {risk:g}% would take open risk to {total + risk:.2f}%, above the {MAX_RISK_TOTAL:g}% limit "
                        f"(room: {max(0.0, MAX_RISK_TOTAL - total):.2f}%)")
        if n_open + 1 > MAX_OPEN:
            errs.append(f"would be position {n_open + 1}; at most {MAX_OPEN} may be open")
        errs += _check_market(n)
        if is_future(inst):
            fut, ferrs = _validate_future(n, inst, direction, risk, stop, hz, today, ref)
            errs += ferrs
            if not ferrs:
                n = {**n, **fut}
                direction = fut.get("direction", direction)
            if errs:
                errors += [f"{tag}: {e}" for e in errs]
                continue
            total += risk
            n_open += 1
            new.append({**n, "instrument": inst, "direction": direction, "risk_pct": round(risk, 4), "stop": stop,
                        "probability": prob, "horizon": hz.isoformat()})
            continue
        ser = series(marks_rows, inst, actable_only=False)
        if not ser:
            errs.append("no mark for this instrument")
        elif direction in ("long", "short"):
            cur = ser[-1][1]
            if not PX.valid_stop(kind(inst, reg), direction, cur, stop):
                errs.append(f"stop {stop:g} is not on the losing side of the current mark {cur:g}")
            elif risk > 0:
                sz = size(inst, direction, risk, cur, stop, reg, ref)
                if sz["capacity_note"]:
                    errs.append(f"capacity: notional above 10% of daily volume or near the position limit; the most "
                                f"this stop allows is {sz['risk_pct']:.2f}% at risk")
                else:
                    n = {**n, "provisional_capacity": sz["capacity"]}
        if errs:
            errors += [f"{tag}: {e}" for e in errs]
            continue
        total += risk
        n_open += 1
        new.append({**n, "instrument": inst, "direction": direction, "risk_pct": round(risk, 4), "stop": stop,
                    "probability": prob, "horizon": hz.isoformat()})
    if session == "daily_review":
        errors += _check_mandate(ans, total, today)
        if today >= C06_FROM:
            closed = {r["id"] for r in reviews if r["action"] == "close"}
            held = {pos[i]["open"]["instrument"] for i in open_ids if i not in closed} | {n["instrument"] for n in new}
            errs, _ = _check_min_positions(ans, n_open, held, marks_rows, today)
            errors += errs + _check_event_reason(ans, today)
        if today >= C07_FROM:
            errors += _check_c07(ans, records, pos, open_ids, reviews, new, n_open, today, now)
    return reviews, new, errors


def _valid_sources(xs) -> list[dict]:
    return [x for x in (xs or []) if isinstance(x, dict) and _url_ok(x.get("url"))]


def non_trading_day(ans: dict, today: date) -> bool:
    """A weekend, or a market holiday named in the proposal (``market_holiday``)."""
    return today.weekday() >= 5 or bool(str(ans.get("market_holiday") or "").strip())


def _check_mandate(ans: dict, risk_after: float, today: date) -> list[str]:
    """The 2026-11-09 mandate: research is required (sources_read), and the account normally holds 3-10% at risk.
    Below 3% only with a specific written reason tied to an identifiable event or condition (below_budget), or, on a
    weekend or market holiday, with the researched ideas named for the next trading day (deferred_ideas)."""
    errs = []
    if not _valid_sources(ans.get("sources_read")):
        errs.append("sources_read is empty: every daily review must research the main drivers across its universe ("
                    + ", ".join(RESEARCH_DRIVERS) + ") on the web before deciding and list what it read with URLs; "
                    "a review without it counts as failed")
    deferred, d_risk = [], 0.0
    for i, d in enumerate(ans.get("deferred_ideas") or [], 1):
        tag = f"deferred idea {i}"
        if not isinstance(d, dict):
            errs.append(f"{tag}: must be an object")
            continue
        inst = str(d.get("instrument", "")).strip().upper()
        try:
            r, pr, mp = float(d.get("risk_pct")), float(d.get("probability")), float(d.get("market_probability"))
        except (TypeError, ValueError):
            errs.append(f"{tag}: risk_pct, probability and market_probability must be numbers")
            continue
        bad = [m for m, ok in ((f"{inst or '?'} is not in the universe", inst in UNIVERSE),
                               ("direction is required", str(d.get("direction") or "").strip()),
                               (f"risk_pct {r:g} must be in (0, {MAX_RISK_POS:g}]", 0 < r <= MAX_RISK_POS + 1e-9),
                               ("probability and market_probability must be in (0, 100]", 0 < pr <= 100 and 0 < mp <= 100),
                               ("thesis is required", str(d.get("thesis") or "").strip())) if not ok]
        errs += [f"{tag}: {m}" for m in bad]
        if not bad:
            deferred.append(d)
            d_risk += r
    if ans.get("deferred_ideas") and not non_trading_day(ans, today):
        errs.append("deferred_ideas are for weekend and market-holiday reviews only: on a trading day, open them")
    if risk_after >= RISK_BUDGET[0] - 1e-9:
        return errs
    if non_trading_day(ans, today) and deferred and risk_after + d_risk >= RISK_BUDGET[0] - 1e-9:
        return errs
    bb = ans.get("below_budget")
    head = (f"the account's risk after this review is {risk_after:.2f}%, below the {RISK_BUDGET[0]:g}% "
            f"budget ({RISK_BUDGET[0]:g}-{RISK_BUDGET[1]:g}%, normally {TYPICAL_POSITIONS[0]}-{TYPICAL_POSITIONS[1]} "
            "positions): open your best ideas, sized by conviction and edge over the market probability, ")
    if not isinstance(bb, dict):
        return errs + [head + "or give below_budget: {\"condition\": the identifiable event or condition, \"until\": "
                              "YYYY-MM-DD when it resolves or is reassessed, \"reasoning\": why it justifies holding less}"]
    cond, why = " ".join(str(bb.get("condition") or "").split()), " ".join(str(bb.get("reasoning") or "").split())
    until = parse_date(bb.get("until"))
    if len(cond) < 15 or GENERIC_REASON.search(cond):
        errs.append("below_budget.condition must name a specific event or condition (for example a dated central-bank "
                    "decision, a data release or a vote), not a general lack of edge")
    if not why:
        errs.append("below_budget.reasoning is required")
    if not until or not (today <= until <= today + timedelta(days=BELOW_BUDGET_MAX_DAYS)):
        errs.append(f"below_budget.until must be a date from today to {BELOW_BUDGET_MAX_DAYS} days ahead")
    return errs


def next_trading_day(d: date) -> date:
    """The next weekday after ``d`` (C06: an event-based reason expires at the end of this day)."""
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _stale_weekdays(last: date | None, today: date) -> int | None:
    """Weekdays strictly between the latest mark and today with no mark (None: no mark at all)."""
    if last is None:
        return None
    return sum(1 for k in range(1, (today - last).days) if (last + timedelta(days=k)).weekday() < 5)


def _is_stale(last: date | None, today: date) -> bool:
    n = _stale_weekdays(last, today)
    return n is None or n >= DATA_STALE_WEEKDAYS


def _norm_url(u: str) -> str:
    return str(u or "").strip().rstrip("/").lower()


def official_calendar(u) -> bool:
    if not _url_ok(u):
        return False
    host = re.sub(r"^https?://", "", u.strip().lower()).split("/")[0].split(":")[0]
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_CALENDAR_HOSTS)


MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                      "dec"), 1)}


def _dates_named(text: str) -> list[tuple[int, int]]:
    """(month, day) pairs written in a reason: '12 Nov', 'Nov 12', '2026-11-12'."""
    out = [(int(m), int(d)) for m, d in re.findall(r"\b\d{4}-(\d{2})-(\d{2})\b", text)]
    out += [(MONTHS[m[:3].lower()], int(d)) for d, m in
            re.findall(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b", text, re.I)]
    out += [(MONTHS[m[:3].lower()], int(d)) for m, d in
            re.findall(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\b", text, re.I)]
    return out


def _check_event_reason(ans: dict, today: date) -> list[str]:
    """C06 rule 2: an event-based below_budget reason cites the event's date (event_date) from an official calendar
    (calendar_url, listed in sources_read), and expires at the end of the next trading day after the event."""
    bb = ans.get("below_budget")
    if not isinstance(bb, dict):
        return []
    cond = " ".join(str(bb.get("condition") or "").split())
    if not (str(bb.get("type") or "").lower() == "event" or bb.get("event_date") or bb.get("calendar_url")
            or EVENT_REASON.search(cond)):
        return []
    errs, ed, url = [], parse_date(bb.get("event_date")), str(bb.get("calendar_url") or "").strip()
    head = "below_budget is tied to an event (C06): "
    if not ed:
        errs.append(head + "event_date (YYYY-MM-DD) is required, the event's date as the official calendar lists it")
    if not official_calendar(url):
        errs.append(head + "calendar_url must be the official calendar that dates the event (the statistics office, "
                    "central bank or official body: " + ", ".join(OFFICIAL_CALENDAR_HOSTS) + ")")
    elif _norm_url(url) not in {_norm_url(x["url"]) for x in _valid_sources(ans.get("sources_read"))}:
        errs.append(head + f"calendar_url {url} must also be listed in sources_read (read it in this review)")
    if ed:
        named = _dates_named(cond)
        if named and (ed.month, ed.day) not in named:
            errs.append(head + f"the condition dates the event differently from event_date {ed}: use the official date")
        exp = next_trading_day(ed)
        until = parse_date(bb.get("until"))
        if exp < today:
            errs.append(head + f"the event on {ed} has passed; a reason tied to it expired at the end of {exp}")
        elif until and until > exp:
            errs.append(head + f"below_budget.until {until} is after its expiry: an event-based reason expires at the "
                        f"end of the next trading day after the event ({exp}); set until to {exp} or earlier")
    return errs


def _check_min_positions(ans: dict, n_after: int, held: set[str], marks_rows: list[dict], today: date,
                         settle_rows: list[dict] | None = None) -> tuple[list[str], list[dict]]:
    """C06 rule 1: at least 2 open positions at all times. below_budget may let risk fall below 3%, never the
    position count. Fewer than 2 only for a named data failure (data_failure: which mark, how stale), verified
    against the marks here, and only for the instruments affected: while enough other instruments have current
    marks, the minimum stands. On a weekend or market holiday, named deferred ideas count (as for the 3% budget).
    Returns (errors, the verified data-failure entries)."""
    deferred = [d for d in (ans.get("deferred_ideas") or [])
                if isinstance(d, dict) and str(d.get("instrument", "")).strip().upper() in UNIVERSE]
    if today >= C07_FROM:
        # C07 rule 4: a deferred idea counts only if its instrument's market is closed on the review date
        have = n_after + len(deferred_toward_minimum(ans, today)[0])
    else:
        have = n_after + (len(deferred) if non_trading_day(ans, today) else 0)
    if have >= MIN_POSITIONS:
        return [], []
    short = MIN_POSITIONS - have
    head = (f"the book would hold {n_after} position(s) after this review; C06 requires at least {MIN_POSITIONS} at "
            "all times: below_budget may let risk fall below 3% (for example two 0.25% positions) but never the "
            "number of positions. Fewer is allowed only for a named data failure, and only for the instruments "
            "affected")
    df = ans.get("data_failure")
    if not df:
        return [head + ": open your best ideas sized small, or give data_failure: [{\"instrument\", \"mark\": which mark "
                       "failed (source and series), \"last_mark\": the date of its latest mark or \"none\"}]"], []
    snap = {r["instrument"]: r for r in market_snapshot(marks_rows, today, settle_rows)}
    errs, ok = [], []
    for i, d in enumerate(df if isinstance(df, list) else [df], 1):
        tag = f"data_failure {i}"
        if not isinstance(d, dict):
            errs.append(f"{tag}: must be an object")
            continue
        inst = str(d.get("instrument", "")).strip().upper()
        if inst not in UNIVERSE:
            errs.append(f"{tag}: {inst or '?'} is not in the universe")
            continue
        if len(" ".join(str(d.get("mark") or "").split())) < 5:
            errs.append(f"{tag} ({inst}): mark is required: which mark failed (its source and series)")
        if "last_mark" not in d:
            errs.append(f"{tag} ({inst}): last_mark is required: the date of its latest mark, or \"none\"")
            continue
        actual = parse_date(snap[inst].get("mark_date"))
        stated = d.get("last_mark")
        stated_d = None if str(stated or "").strip().lower() in ("", "none", "null") else parse_date(stated)
        if stated_d != actual:
            errs.append(f"{tag} ({inst}): last_mark {stated!r} does not match its latest mark "
                        f"({actual.isoformat() if actual else 'none'})")
            continue
        if not _is_stale(actual, today):
            errs.append(f"{tag} ({inst}): its latest mark ({actual}) is current, {_stale_weekdays(actual, today)} "
                        f"weekday(s) old (stale means at least {DATA_STALE_WEEKDAYS}): not a data failure")
            continue
        ok.append({**d, "instrument": inst, "stale_weekdays": _stale_weekdays(actual, today)})
    affected = {d["instrument"] for d in ok}
    fresh = sorted(i for i, r in snap.items() if i not in held and i not in affected
                   and not _is_stale(parse_date(r.get("mark_date")), today))
    if len(fresh) >= short:
        errs.append(head + f": the data failure covers only {', '.join(sorted(affected)) or 'no instrument'}, and "
                    f"{len(fresh)} other instrument(s) have current marks ({', '.join(fresh)}): open at least {short} "
                    "position(s) there")
    return errs, (ok if not errs else [])


# ----------------------------------------------------------------------------- config change C07
def _inst(x) -> str:
    return str((x or {}).get("instrument", "") if isinstance(x, dict) else "").strip().upper()


def _dir(x) -> str:
    return str((x or {}).get("direction", "") if isinstance(x, dict) else "").strip().lower()


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _check_no_coin_flips(ans: dict) -> list[str]:
    """C07 rule 1: no 50% calls. Every opened position's stated probability differs from 50 (no view); so does every
    deferred idea's, since it must open at the next session."""
    errs = []
    for key, what in (("new_positions", "new position"), ("deferred_ideas", "deferred idea")):
        for i, n in enumerate(ans.get(key) or [], 1):
            p = _num(n.get("probability")) if isinstance(n, dict) else None
            if p is not None and abs(p - NO_VIEW_PROBABILITY) < 1e-9:
                errs.append(f"{what} {i} ({_inst(n) or '?'}): probability 50 is not a call (C07): state the side you "
                            "favour (for example 55 or 45 with the direction flipped), or do not open it")
    return errs


def market_calendar(u) -> bool:
    """An official calendar (OFFICIAL_CALENDAR_HOSTS) or an exchange / market-association calendar
    (MARKET_CALENDAR_HOSTS): what a weekday market closure may cite (C07 rule 4)."""
    if official_calendar(u):
        return True
    if not _url_ok(u):
        return False
    host = re.sub(r"^https?://", "", u.strip().lower()).split("/")[0].split(":")[0]
    return any(host == h or host.endswith("." + h) for h in MARKET_CALENDAR_HOSTS)


def market_closed(d: dict, today: date, ans: dict) -> tuple[bool, str | None]:
    """C07 rule 4: is this deferred idea's market closed on the review date? Every market is closed on a weekend. FX
    trades every weekday except 1 Jan and 25 Dec. Any other market on a weekday is closed only with
    ``market_closed`` {holiday, calendar_url}: an official or exchange calendar, listed in sources_read.
    Returns (closed, an error when a stated closure does not hold up, else None)."""
    if today.weekday() >= 5:
        return True, None
    inst = _inst(d)
    mc = d.get("market_closed")
    if UNIVERSE.get(inst, {}).get("asset_class") == "fx":
        closed = (today.month, today.day) in FX_CLOSED_DAYS
        return closed, (None if closed or not mc else
                        f"{inst}: FX trades every weekday except 1 Jan and 25 Dec, so its market is open on {today}")
    if not mc:
        return False, None
    if not isinstance(mc, dict):
        return False, f"{inst}: market_closed must be {{\"holiday\", \"calendar_url\"}}"
    url = str(mc.get("calendar_url") or "").strip()
    if len(" ".join(str(mc.get("holiday") or "").split())) < 3:
        return False, f"{inst}: market_closed.holiday is required (the holiday that closes this market on {today})"
    if not market_calendar(url):
        return False, (f"{inst}: market_closed.calendar_url must be the exchange's or an official holiday calendar ("
                       + ", ".join(MARKET_CALENDAR_HOSTS) + ", or an official calendar host)")
    if _norm_url(url) not in {_norm_url(x["url"]) for x in _valid_sources(ans.get("sources_read"))}:
        return False, f"{inst}: market_closed.calendar_url {url} must also be listed in sources_read"
    return True, None


def deferred_toward_minimum(ans: dict, today: date) -> tuple[list[dict], list[str]]:
    """C07 rule 4: the deferred ideas that count toward the C06 two-position minimum (those whose market is closed on
    the review date), and the errors of any stated closure that does not hold up."""
    out, errs = [], []
    for i, d in enumerate(ans.get("deferred_ideas") or [], 1):
        if not isinstance(d, dict) or _inst(d) not in UNIVERSE:
            continue
        closed, err = market_closed(d, today, ans)
        if err:
            errs.append(f"deferred idea {i} ({_inst(d)}): {err.split(': ', 1)[1]} (C07)")
        if closed:
            out.append(d)
    return out, errs


def _check_deferred_followup(ans: dict, records: list[dict], pos: dict[str, dict], new: list[dict],
                             today: date) -> list[str]:
    """C07 rule 4: an idea deferred by the latest accepted daily review before today must open at the next session:
    this review opens it (same instrument and direction) unless its market is still closed today, in which case it is
    carried forward in deferred_ideas."""
    prior = [r for r in records if r.get("type") == "run" and r.get("session") == "daily_review"
             and r.get("status") != "failed" and (parse_date(r.get("date")) or date.min) >= C07_FROM
             and parse_date(r.get("date")) < today]
    if not prior or not prior[-1].get("deferred_ideas"):
        return []
    last = prior[-1]
    since = parse_date(last["date"])
    carried = {(_inst(d), _dir(d)) for d in deferred_toward_minimum(ans, today)[0]}
    errs = []
    for d in last["deferred_ideas"]:
        key = (_inst(d), _dir(d))
        if any((n["instrument"], str(n["direction"]).lower()) == key for n in new):
            continue
        if any((p["open"]["instrument"], str(p["open"]["direction"]).lower()) == key
               and (parse_date(p["open"].get("decision_date")) or date.min) >= since for p in pos.values()):
            continue
        if key in carried:
            continue
        errs.append(f"deferred idea {key[1]} {key[0]} from the {since} review must open at the next session (C07): "
                    "open it in new_positions (same instrument and direction), or, only while its market is still "
                    "closed today, carry it forward in deferred_ideas")
    return errs


def _check_candidates(ans: dict, new: list[dict], counted_deferred: list[dict], binds: bool) -> list[str]:
    """C07 rule 2. When the C06 two-position minimum binds, the review lists at least 5 candidates (distinct
    instruments) across at least 2 asset classes (rates, FX, commodities), including every position it opens or
    defers. A candidate the review dropped after The Opposition may be reopened (opened or deferred) only with a
    reopen_reason stating why no other candidate is better, naming each candidate not opened."""
    cands = ans.get("candidates")
    head = ("the C06 two-position minimum binds in this review (the book held fewer than 2 and this review brings it "
            "to exactly 2), so C07 requires a wider search: ")
    if not cands:
        return [head + f"list at least {MIN_CANDIDATES} candidates across at least {MIN_CANDIDATE_CLASSES} asset "
                       "classes in candidates: [{\"instrument\", \"direction\", \"probability\", \"market_probability\", "
                       "\"outcome\": opened|deferred|not_opened, \"opposition\": kept|dropped|none, \"reason\"}]"] \
            if binds else []
    if not isinstance(cands, list):
        return ["candidates must be a list (C07)"]
    errs, good = [], []
    for i, c in enumerate(cands, 1):
        inst = _inst(c)
        tag = f"candidate {i} ({inst or '?'})"
        if not isinstance(c, dict):
            errs.append(f"{tag}: must be an object (C07)")
            continue
        out, opp = str(c.get("outcome") or "").strip().lower(), str(c.get("opposition") or "").strip().lower()
        pr, mp = _num(c.get("probability")), _num(c.get("market_probability"))
        bad = [m for m, ok in ((f"not in the universe", inst in UNIVERSE),
                               ("direction is required", _dir(c)),
                               ("probability and market_probability must be numbers in (0, 100]",
                                pr is not None and mp is not None and 0 < pr <= 100 and 0 < mp <= 100),
                               (f"outcome must be one of {', '.join(CANDIDATE_OUTCOMES)}", out in CANDIDATE_OUTCOMES),
                               (f"opposition must be one of {', '.join(OPPOSITION_OUTCOMES)}", opp in OPPOSITION_OUTCOMES),
                               ("reason is required (why it was or was not taken)",
                                len(" ".join(str(c.get("reason") or "").split())) >= 10),
                               ("an opened candidate went through The Opposition: opposition is kept or dropped",
                                not (out == "opened" and opp == "none"))) if not ok]
        if bad:
            errs += [f"{tag}: {m} (C07)" for m in bad]
            continue
        good.append({**c, "_i": i, "_inst": inst, "_out": out, "_opp": opp})
    insts = {c["_inst"] for c in good}
    classes = {CANDIDATE_CLASS.get(UNIVERSE[i]["asset_class"], UNIVERSE[i]["asset_class"]) for i in insts}
    if binds and len(insts) < MIN_CANDIDATES:
        errs.append(head + f"candidates name {len(insts)} distinct instrument(s); at least {MIN_CANDIDATES} are required")
    if binds and len(classes) < MIN_CANDIDATE_CLASSES:
        errs.append(head + f"candidates span {len(classes)} asset class(es) ({', '.join(sorted(classes)) or 'none'}); "
                           f"at least {MIN_CANDIDATE_CLASSES} of rates, fx and commodities are required")
    listed = {(c["_inst"], _dir(c), c["_out"]) for c in good}
    for n in new:
        if (n["instrument"], str(n["direction"]).lower(), "opened") not in listed:
            errs.append(f"candidates must list every opened position as outcome 'opened': {n['direction']} "
                        f"{n['instrument']} is missing (C07)")
    for d in counted_deferred:
        if (_inst(d), _dir(d), "deferred") not in listed:
            errs.append(f"candidates must list every deferred idea as outcome 'deferred': {_dir(d)} {_inst(d)} is "
                        "missing (C07)")
    opened = {(n["instrument"], str(n["direction"]).lower()) for n in new}
    deferred = {(_inst(d), _dir(d)) for d in (ans.get("deferred_ideas") or []) if isinstance(d, dict)}
    for c in good:
        key = (c["_inst"], _dir(c))
        if (c["_out"] == "opened" and key not in opened) or (c["_out"] == "deferred" and key not in deferred):
            errs.append(f"candidate {c['_i']} ({c['_inst']}): outcome {c['_out']}, but {key[1]} {key[0]} is not in "
                        f"{'new_positions' if c['_out'] == 'opened' else 'deferred_ideas'} (C07)")
    others = sorted({c["_inst"] for c in good if c["_out"] == "not_opened"})
    for c in good:
        if c["_opp"] != "dropped" or c["_out"] == "not_opened":
            continue
        why = " ".join(str(c.get("reopen_reason") or "").split())
        tag = f"candidate {c['_i']} ({c['_inst']})"
        missing = [o for o in others if not re.search(rf"(?<![A-Z0-9-]){re.escape(o)}(?![A-Z0-9-])", why)]
        if len(why) < 40:
            errs.append(f"{tag}: dropped after The Opposition and reopened: reopen_reason must state why no other "
                        "candidate is better (C07)")
        elif missing:
            errs.append(f"{tag}: reopen_reason must say why each other candidate is not better; it does not name "
                        f"{', '.join(missing)} (C07)")
    return errs


# Time anchor (C07 rule 3)
_MONTH = (r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:tember|t)?|"
          r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}})(?:\s*[-–]\s*(\d{{1,2}}))?\s+{_MONTH}\b")
_MONTH_DAY = re.compile(rf"\b{_MONTH}\.?\s+(\d{{1,2}})(?:\s*[-–]\s*(\d{{1,2}}))?\b(?!\s*[:.]\d)")
_ISO_DATE = re.compile(r"\b\d{4}-(\d{2})-(\d{2})\b")
# Scheduled events a reason or thesis may cite by name; time_anchor.events must cover each one named
EVENT_TERMS = {
    "CPI": (r"CPI", r"consumer prices?"), "PCE": (r"PCE",), "PPI": (r"PPI", r"producer prices?"), "HICP": (r"HICP",),
    "payrolls": (r"payrolls?", r"NFP", r"jobs report", r"employment (report|situation)"), "GDP": (r"GDP",),
    "retail sales": (r"retail sales",), "PMI": (r"PMIs?",), "ISM": (r"ISM",), "FOMC": (r"FOMC",), "MPC": (r"MPC",),
    "rate decision": (r"rate decision", r"policy (decision|meeting)"), "OPEC": (r"OPEC\+?",), "WASDE": (r"WASDE",),
    "election": (r"elections?", r"midterms?"), "referendum": (r"referendum",), "auction": (r"auctions?",)}
_TERM_RE = {g: re.compile(r"\b(" + "|".join(ts) + r")(?![A-Za-z])", re.I) for g, ts in EVENT_TERMS.items()}
# Words that describe an event as having happened, and words before them that keep it in the future
_OUT_RE = re.compile(r"\b(released|published|announced|came in|printed|showed|surprised|beat|missed|topped|hiked|"
                     r"delivered)\b", re.I)
_NOT_YET = {"will", "to", "once", "when", "until", "before", "if", "unless", "not", "yet", "due", "scheduled",
            "expected", "set", "await", "awaits", "awaiting", "ahead", "whether", "could", "would", "may", "might",
            "should", "can", "never", "is", "are", "be", "being", "isn't", "aren't", "hasn't", "haven't", "won't"}
_CLAUSE_SPLIT = re.compile(r"[,;:](?=\s)|[()]|\.(?=\s|$)|\s(?:and|but|while|whereas|although|though)\s|\s[-–—]\s")
_MONTH_WORD = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b")


def _named_dates(text: str) -> list[set[tuple[int, int]]]:
    """Each date written in ``text`` as a set of (month, day): '10 Nov', 'Nov 10', '2026-11-10', a range '8-9 Dec'."""
    out = [{(int(m), int(d))} for m, d in _ISO_DATE.findall(text)]
    for d1, d2, mon in _DAY_MONTH.findall(text):
        out.append({(MONTHS[mon[:3].lower()], int(x)) for x in (d1, d2) if x})
    for mon, d1, d2 in _MONTH_DAY.findall(text):
        out.append({(MONTHS[mon[:3].lower()], int(x)) for x in (d1, d2) if x})
    return [s for s in out if all(1 <= d <= 31 for _, d in s)]


def _terms(text: str) -> set[str]:
    return {g for g, rx in _TERM_RE.items() if rx.search(text)}


def _described_as_out(clause: str) -> str | None:
    """The word that describes an event as having happened (e.g. 'released'), unless the words just before it keep
    it in the future or negate it ('is due to be released', 'has not been released')."""
    for m in _OUT_RE.finditer(clause):
        before = re.findall(r"[a-z']+", clause[:m.start()].lower())[-3:]
        if before and (before[-1] in _NOT_YET or any(w in ("not", "yet", "never", "will", "won't", "to", "until",
                                                          "before", "once", "if", "unless", "whether")
                                                     for w in before)):
            continue
        return m.group(1)
    return None


def _anchor_texts(ans: dict) -> list[tuple[str, str]]:
    """(label, text) of every reason and thesis in a review (C07 rule 3), and its market summary."""
    out = [("market_summary", ans.get("market_summary")), ("no_trade_reasoning", ans.get("no_trade_reasoning"))]
    bb = ans.get("below_budget")
    if isinstance(bb, dict):
        out += [("below_budget.condition", bb.get("condition")), ("below_budget.reasoning", bb.get("reasoning"))]
    for r in ans.get("reviews") or []:
        if isinstance(r, dict):
            out.append((f"review of {str(r.get('id') or '?').strip()}", r.get("reasoning")))
    for key, what in (("new_positions", "new position"), ("deferred_ideas", "deferred idea")):
        for i, n in enumerate(ans.get(key) or [], 1):
            if isinstance(n, dict):
                out.append((f"{what} {i} ({_inst(n) or '?'}) thesis", n.get("thesis")))
    for i, c in enumerate(ans.get("candidates") or [] if isinstance(ans.get("candidates"), list) else [], 1):
        if isinstance(c, dict):
            out += [(f"candidate {i} ({_inst(c) or '?'}) reason", c.get("reason")),
                    (f"candidate {i} ({_inst(c) or '?'}) reopen_reason", c.get("reopen_reason"))]
    for i, f in enumerate(ans.get("forecasts") or [] if isinstance(ans.get("forecasts"), list) else [], 1):
        if isinstance(f, dict):                      # C08: a forecast's reasoning is Janus's own text
            out.append((f"forecast {i} ({_inst(f) or '?'}) reasoning", f.get("reasoning")))
    return [(lbl, " ".join(str(t).split())) for lbl, t in out if t and str(t).strip()]


def _parse_utc(s) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None or t.utcoffset() != timedelta(0):
        return None
    return t


def _check_time_anchor(ans: dict, now: datetime) -> list[str]:
    """C07 rule 3. The review records its current UTC time (time_anchor.now_utc) and, for every event cited in a
    reason or thesis, whether it had already occurred at that time (time_anchor.events: {event, time_utc (or date
    when it is not on the review's own UTC date), occurred}). The CLI checks that now_utc is the time of the review,
    that each occurred flag agrees with the event's time, that every date and scheduled event named in a reason or
    thesis is in the list, and that no event dated in the future is described as released."""
    ta = ans.get("time_anchor")
    head = "time_anchor (C07): "
    if not isinstance(ta, dict):
        return [head + "required: {\"now_utc\": the review's current UTC time (YYYY-MM-DDTHH:MM:SSZ), \"events\": [{\"event\", "
                       "\"time_utc\" (or \"date\" when not on the review's UTC date), \"occurred\": true|false}] for every "
                       "event cited in a reason or thesis}"]
    anchor = _parse_utc(ta.get("now_utc"))
    if anchor is None:
        return [head + "now_utc must be the review's current UTC time, e.g. 2026-11-10T23:07:00Z (UTC, with Z or +00:00)"]
    errs = []
    if anchor > now + ANCHOR_MAX_AHEAD or anchor < now - ANCHOR_MAX_AGE:
        errs.append(head + f"now_utc {anchor.isoformat()} is not the time of this review (the CLI's clock is "
                    f"{now.replace(microsecond=0).isoformat()}; now_utc may be at most {ANCHOR_MAX_AGE} old): check the "
                    "time with `date -u` and re-check every event against it")
    events = []
    for i, e in enumerate(ta.get("events") or [] if isinstance(ta.get("events"), list) else [], 1):
        if not isinstance(e, dict) or len(" ".join(str(e.get("event") or "").split())) < 3:
            errs.append(head + f"event {i}: needs a name (event)")
            continue
        name = " ".join(str(e["event"]).split())
        tag = head + f"event {i} ({name[:60]})"
        when = _parse_utc(e.get("time_utc")) if e.get("time_utc") else None
        day = when.date() if when else parse_date(e.get("date"))
        occ = e.get("occurred")
        if e.get("time_utc") and when is None:
            errs.append(tag + ": time_utc must be a UTC time, e.g. 2026-11-10T13:30:00Z")
            continue
        if day is None:
            errs.append(tag + ": time_utc (or date) is required")
            continue
        if not isinstance(occ, bool):
            errs.append(tag + ": occurred must be true or false (had it happened at now_utc?)")
            continue
        if when is None and day == anchor.date():
            errs.append(tag + f": it is on the review's own UTC date ({day}): give time_utc, so whether it has "
                        "happened can be checked")
            continue
        happened = (when <= anchor) if when else (day < anchor.date())
        if occ and ((when and when > now + ANCHOR_MAX_AHEAD) or (not when and day > now.date())):
            errs.append(tag + f": dated in the future ({when.isoformat() if when else day}, after the CLI's clock "
                        f"{now.replace(microsecond=0).isoformat()}), so it cannot have occurred or been released")
        elif occ != happened:
            errs.append(tag + f": occurred is {str(occ).lower()}, but at now_utc {anchor.isoformat()} the event "
                        f"({when.isoformat() if when else day}) " + ("had already happened" if happened else
                                                                     "had not yet happened"))
        events.append({"name": name, "day": day, "when": when, "occurred": occ and happened,
                       "terms": _terms(name)})
    for lbl, text in _anchor_texts(ans):
        for ds in _named_dates(text):
            if not any((ev["day"].month, ev["day"].day) in ds for ev in events):
                d0 = sorted(ds)[-1]
                errs.append(head + f"{lbl} names {d0[1]} {calendar.month_abbr[d0[0]]}, but time_anchor.events has no "
                            "event on that date: list it, with whether it had occurred at now_utc")
        for g in sorted(_terms(text)):
            if not any(g in ev["terms"] for ev in events):
                errs.append(head + f"{lbl} cites {g}, but no event in time_anchor.events names it: list it, with its "
                            "date and whether it had occurred at now_utc")
        for clause in _CLAUSE_SPLIT.split(text):
            word = _described_as_out(clause or "")
            if not word:
                continue
            ds, gs = _named_dates(clause), _terms(clause)
            if ds:
                hit = [ev for ev in events if any((ev["day"].month, ev["day"].day) in s for s in ds)
                       and (not gs or ev["terms"] & gs or not any(e2["terms"] & gs for e2 in events))]
                future = [ev for ev in hit if not ev["occurred"]]
            elif gs:
                hit = [ev for ev in events if ev["terms"] & gs]
                months = set(_MONTH_WORD.findall(clause))
                if months and any(m in ev["name"] for ev in hit for m in months):
                    hit = [ev for ev in hit if any(m in ev["name"] for m in months)]
                future = hit if hit and all(not ev["occurred"] for ev in hit) else []
            else:
                continue
            if future:
                ev = future[0]
                errs.append(head + f"{lbl} describes {ev['name'][:60]} as '{word.lower()}', but at now_utc "
                            f"{anchor.isoformat()} it had not yet happened "
                            f"({ev['when'].isoformat() if ev['when'] else ev['day']}): an event dated in the future "
                            "cannot be described as released")
    return list(dict.fromkeys(errs))


def _check_c07(ans: dict, records: list[dict], pos: dict[str, dict], open_ids: list[str], reviews: list[dict],
               new: list[dict], n_after: int, today: date, now: datetime) -> list[str]:
    """Config change C07 (approved 2026-11-10): every rule, for a daily review from C07_FROM."""
    closed = {r["id"] for r in reviews if r["action"] == "close"}
    held_before = sum(1 for i in open_ids if i not in closed)
    counted, errs = deferred_toward_minimum(ans, today)
    binds = held_before < MIN_POSITIONS and n_after + len(counted) == MIN_POSITIONS
    errs = _check_no_coin_flips(ans) + errs
    errs += _check_candidates(ans, new, counted, binds)
    errs += _check_time_anchor(ans, now)
    errs += _check_deferred_followup(ans, records, pos, new, today)
    return errs


# ----------------------------------------------------------------------------- config change C08
def _watchlist_doc(path: Path | None = None) -> dict:
    import yaml
    return yaml.safe_load((path or WATCHLIST_FILE).read_text(encoding="utf-8"))


def load_clusters(path: Path | None = None) -> dict[str, list[str]]:
    """C09: the correlation clusters of janus/watchlist.yaml, {cluster: [instruments]} in file order (a cluster may
    be empty, e.g. gold while no free daily mark exists). The fund rule counts one call per cluster per window."""
    return {str(c["cluster"]): [str(i).strip().upper() for i in (c.get("instruments") or [])]
            for c in _watchlist_doc(path).get("clusters") or []}


def load_watchlist(path: Path | None = None) -> list[dict]:
    """The C08 watchlist (janus/watchlist.yaml): instrument, question, yes_if, yes_position, resolution_source,
    stop, with the file's horizon_trading_days and the instrument's cluster (C09) on each entry."""
    doc = _watchlist_doc(path)
    h = int(doc["horizon_trading_days"])
    of = {i: c for c, ms in load_clusters(path).items() for i in ms}
    return [{**w, "instrument": str(w["instrument"]).strip().upper(), "horizon_trading_days": h,
             "cluster": of.get(str(w["instrument"]).strip().upper()),
             "question": " ".join(str(w["question"]).split()),
             "resolution_source": " ".join(str(w["resolution_source"]).split())} for w in doc["instruments"]]


def add_weekdays(d: date, n: int) -> date:
    """The ``n``-th weekday after ``d`` (C08: 20 trading days = 20 weekdays after the base mark's date)."""
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def _whole_probability(x) -> int | None:
    v = _num(x)
    return int(v) if v is not None and float(v).is_integer() else None


def _check_forecasts(ans: dict, wl: list[dict]) -> tuple[list[str], list[dict]]:
    """C08 rule 2: a forecast for every watchlist instrument, each with p_initial (before The Opposition) and
    p_final, whole numbers from 1 to 99 and never 50, a reason and The Opposition's case (advisory: it never vetoes a
    forecast, and nothing here compares it with the probabilities)."""
    head = "forecasts (C08): "
    names = [w["instrument"] for w in wl]
    fc = ans.get("forecasts")
    if not isinstance(fc, list) or not fc:
        return [head + "required: one forecast for every watchlist instrument (" + ", ".join(names) + "), each "
                "{\"instrument\", \"p_initial\" (before The Opposition), \"p_final\", \"reasoning\", \"opposition\": "
                "{\"case_against\", \"probability_view_wrong\", \"model\"}}, probabilities whole numbers from 1 to 99, "
                "never 50"], []
    errs, out, seen = [], [], set()
    lo, hi = C08_PROBABILITY_RANGE
    for i, f in enumerate(fc, 1):
        inst = _inst(f)
        tag = f"forecast {i} ({inst or '?'})"       # first, so a withheld futures error still names it
        if not isinstance(f, dict):
            errs.append(tag + ": must be an object (C08)")
            continue
        if inst not in names:
            errs.append(tag + ": not on the watchlist (janus/watchlist.yaml: " + ", ".join(names) + ") (C08)")
            continue
        if inst in seen:
            errs.append(tag + ": forecast twice (C08)")
            continue
        seen.add(inst)
        bad, ps = [], {}
        for k in ("p_initial", "p_final"):
            v = _whole_probability(f.get(k))
            if v is None or not (lo <= v <= hi):
                bad.append(f"{k} must be a whole number from {lo} to {hi} (got {f.get(k)!r})")
            elif v == NO_VIEW_PROBABILITY:
                bad.append(f"{k} is 50, which is not a forecast: give the side you favour (1-49 or 51-99)")
            else:
                ps[k] = v
        if len(" ".join(str(f.get("reasoning") or "").split())) < 10:
            bad.append("reasoning is required (why this probability)")
        opp = f.get("opposition")
        if not isinstance(opp, dict) or len(" ".join(str(opp.get("case_against") or "").split())) < 10:
            bad.append("opposition.case_against is required: The Opposition's case against this forecast (advisory; "
                       "it never vetoes a forecast)")
        mkt = {k: f[k] for k in ("market_probability", "market_basis", "market_source") if f.get(k) not in (None, "")}
        if mkt:
            bad += _check_market(f)
        else:                       # C04 amendment: no market-implied probability -> 50, basis none (a coin flip)
            mkt = {"market_probability": COIN_FLIP, "market_basis": "none",
                   "market_source": "no market-implied probability for a 20-trading-day direction: coin flip (0.50)"}
        if bad:
            errs += [f"{tag}: {b} (C08)" for b in bad]
            continue
        out.append({"instrument": inst, **ps, "reasoning": " ".join(str(f["reasoning"]).split()),
                    "opposition": {k: opp.get(k) for k in ("case_against", "key_risks", "probability_view_wrong",
                                                           "sources", "model") if k in opp},
                    "market_probability": float(mkt["market_probability"]),
                    "market_basis": str(mkt["market_basis"]).strip().lower(),
                    "market_source": " ".join(str(mkt["market_source"]).split())})
    missing = [n for n in names if n not in seen]
    if missing:
        errs.append(head + "every daily review gives a probability for every watchlist instrument; missing "
                    + ", ".join(missing))
    return errs, out


def _check_c08_data_failures(ans: dict, wl: list[dict], marks_rows: list[dict], today: date) -> tuple[list[str], dict]:
    """C08 rule 3: only a named data failure on an instrument may exclude it from the book (the C06 format, verified
    against the marks in the same way: last_mark must match, and the mark must be stale). Every other watchlist
    instrument needs a mark to set its stop. Returns (errors, {instrument: verified entry})."""
    names = [w["instrument"] for w in wl]
    last = {n: (series(marks_rows, n, actable_only=False) or [(None,)])[-1][0] for n in names}
    df = ans.get("data_failure") or []
    errs, ok = [], {}
    for i, d in enumerate(df if isinstance(df, list) else [df], 1):
        tag = f"data_failure {i}"
        if not isinstance(d, dict):
            errs.append(f"{tag}: must be an object")
            continue
        inst = _inst(d)
        if inst not in names:
            errs.append(f"{tag}: {inst or '?'} is not on the watchlist (C08 excludes only a watchlist instrument)")
            continue
        if len(" ".join(str(d.get("mark") or "").split())) < 5:
            errs.append(f"{tag} ({inst}): mark is required: which mark failed (its source and series)")
        if "last_mark" not in d:
            errs.append(f"{tag} ({inst}): last_mark is required: the date of its latest mark, or \"none\"")
            continue
        stated = d.get("last_mark")
        stated_d = None if str(stated or "").strip().lower() in ("", "none", "null") else parse_date(stated)
        if stated_d != last[inst]:
            errs.append(f"{tag} ({inst}): last_mark {stated!r} does not match its latest mark "
                        f"({last[inst].isoformat() if last[inst] else 'none'})")
            continue
        if not _is_stale(last[inst], today):
            errs.append(f"{tag} ({inst}): its latest mark ({last[inst]}) is current, "
                        f"{_stale_weekdays(last[inst], today)} weekday(s) old (stale means at least "
                        f"{DATA_STALE_WEEKDAYS}): not a data failure, so it stays in the book (C08)")
            continue
        ok[inst] = {**d, "instrument": inst, "stale_weekdays": _stale_weekdays(last[inst], today)}
    for n in names:
        if last[n] is None and n not in ok:
            errs.append(f"{n} has no mark, so the CLI cannot set its stop: name the data failure in data_failure "
                        "(C08), or wait for the mark")
    return errs, (ok if not errs else {})


def _water_fill(edge: dict[str, float], total: float, cap: float) -> dict[str, float]:
    """Risk proportional to ``edge`` summing to ``total``, no position above ``cap`` (the excess goes to the rest)."""
    out, free, left = {}, dict(edge), total
    while free:
        k = left / sum(free.values())
        over = [i for i, e in free.items() if k * e >= cap - 1e-12]
        if not over:
            out.update({i: k * e for i, e in free.items()})
            break
        for i in over:
            out[i] = cap
            left -= cap
            free.pop(i)
    return out


def c08_targets(final: dict[str, int], excluded=()) -> dict[str, dict]:
    """C08 rule 3: each instrument on the side of its final forecast (above 50: the YES side, long; below: short),
    risk proportional to |p - 50|: C08_RISK_PER_POINT % per point, at most 2% each; when that total is outside C05's
    3-10% band it is scaled to the nearer edge (the 2% cap still holds, its excess spread over the rest)."""
    edge = {i: float(abs(p - NO_VIEW_PROBABILITY)) for i, p in final.items() if i not in set(excluded)}
    if not edge:
        return {}
    base = {i: min(C08_RISK_PER_POINT * e, MAX_RISK_POS) for i, e in edge.items()}
    total = sum(base.values())
    goal = min(max(total, RISK_BUDGET[0]), RISK_BUDGET[1])
    risk = base if abs(goal - total) < 1e-9 else _water_fill(edge, goal, MAX_RISK_POS)
    return {i: {"direction": "long" if final[i] > NO_VIEW_PROBABILITY else "short", "risk_pct": round(risk[i], 6),
                "edge": edge[i]} for i in edge}


def c08_stop(w: dict, k: str, direction: str, level: float) -> float | None:
    """The mechanical stop: ``stop.distance`` from the latest mark on the losing side (yield points, or % of the rate)."""
    d = float(w["stop"]["distance"])
    cands = (level + d, level - d) if w["stop"]["unit"] == "yield_points" else (level * (1 + d / 100),
                                                                               level * (1 - d / 100))
    return next((round(s, 6) for s in cands if PX.valid_stop(k, direction, level, s)), None)


def _held_risk(p: dict) -> float:
    return float((p.get("fill") or p["open"]).get("risk_pct", p["open"]["risk_pct"]))


def c08_plan(records: list[dict], marks_rows: list[dict], today: date, forecasts: list[dict], excluded: dict,
             wl: list[dict]) -> dict:
    """The book the CLI sets at a C08 daily review: closes (every position not set under C08, as rule 5's closing
    action; a side flip; a named data failure; a resize outside the no-trade band) and orders at the next official
    daily mark. A held position on the target side is kept while its target risk is within 25% of its current
    risk, unless keeping it would leave the total outside the 3-10% band."""
    reg, ref, pos = registry_rows(), CAP.load_reference(), positions(records)
    by = {w["instrument"]: w for w in wl}
    final = {f["instrument"]: f["p_final"] for f in forecasts}
    targets = c08_targets(final, excluded)
    live = {pid: p for pid, p in pos.items() if p["status"] in ("open", "pending")}
    actions, holds, opens = [], {}, []
    cur: dict[str, list[str]] = {}
    for pid, p in sorted(live.items()):
        if p["open"].get("c08") and p["open"]["instrument"] in by:
            cur.setdefault(p["open"]["instrument"], []).append(pid)
        else:
            actions.append({"id": pid, "action": "close", "close_reason": "C08 rule 5: discretionary position closed",
                            "reasoning": "Config change C08: the CLI sets the book from the forced forecasts, so every "
                                         "position not set under C08 is closed at the first daily review under C08."})
    for inst, pids in cur.items():
        for extra in pids[1:]:                       # never more than one C08 position per instrument
            actions.append({"id": extra, "action": "close", "close_reason": "C08 duplicate",
                            "reasoning": "C08: one mechanical position per instrument."})
    want = {}
    for w in wl:
        inst = w["instrument"]
        pid = (cur.get(inst) or [None])[0]
        t = targets.get(inst)
        if t is None:
            if pid:
                actions.append({"id": pid, "action": "close", "close_reason": "C08 data failure",
                                "reasoning": f"C08: named data failure on {inst} ({excluded[inst].get('mark')}); "
                                             "the instrument is out of the book until its mark is current."})
            continue
        if pid:
            p = live[pid]
            held = _held_risk(p)
            same = p["open"]["direction"] == t["direction"]
            if same and abs(t["risk_pct"] - held) <= C08_NO_TRADE_BAND * held + 1e-9:
                holds[inst] = (pid, held)
            want[inst] = (pid, same)
        else:
            want[inst] = (None, False)
    if holds:
        after = sum(h for _, h in holds.values()) + sum(targets[i]["risk_pct"] for i in want if i not in holds)
        if after < RISK_BUDGET[0] - 1e-9 <= sum(t["risk_pct"] for t in targets.values()) or \
                after > RISK_BUDGET[1] + 1e-9:
            holds = {}                               # the band would leave the book outside 3-10%: trade to target
    for inst, (pid, same) in want.items():
        t, w = targets[inst], by[inst]
        if inst in holds:
            actions.append({"id": pid, "action": "hold", "reasoning": (
                f"C08: final forecast {final[inst]}% -> {t['direction']} {t['risk_pct']:.2f}% at risk; held at "
                f"{holds[inst][1]:.2f}%, within the {C08_NO_TRADE_BAND:.0%} no-trade band.")})
            continue
        if pid:
            actions.append({"id": pid, "action": "close", "close_reason": "C08 rebalance" if same else "C08 side flip",
                            "reasoning": (f"C08: final forecast {final[inst]}% -> {t['direction']} "
                                          f"{t['risk_pct']:.2f}% at risk; " + (
                                              f"resized from {_held_risk(live[pid]):.2f}% (outside the "
                                              f"{C08_NO_TRADE_BAND:.0%} no-trade band)" if same else
                                              f"side flips from {live[pid]['open']['direction']}") + ".")})
        k = kind(inst, reg)
        ser = series(marks_rows, inst, actable_only=False)
        level = ser[-1][1]
        stop = c08_stop(w, k, t["direction"], level)
        risk, note = t["risk_pct"], ""
        sz = size(inst, t["direction"], risk, level, stop, reg, ref)
        if sz["capacity_note"]:
            risk, note = round(sz["risk_pct"], 6), sz["capacity_note"]
        opens.append({"instrument": inst, "direction": t["direction"], "risk_pct": risk, "target_risk_pct":
                      t["risk_pct"], "stop": stop, "ref_level": level, "ref_date": ser[-1][0].isoformat(),
                      "replaces": pid if (pid and same) else None, "flips": pid if (pid and not same) else None,
                      "capacity_note": note, "provisional_capacity": sz["capacity"]})
    risk_after = sum(h for _, h in holds.values()) + sum(o["risk_pct"] for o in opens)
    return {"targets": targets, "actions": actions, "opens": opens, "risk_after_pct": round(risk_after, 4),
            "excluded": sorted(excluded)}


def validate_c08(ans: dict, records: list[dict], marks_rows: list[dict], today: date, now: datetime,
                 wl: list[dict] | None = None) -> tuple[dict | None, list[str]]:
    """Every rule for a daily review under C08. Returns (the plan, errors); any error rejects the whole review."""
    wl = wl if wl is not None else load_watchlist()
    errors = []
    if not str(ans.get("model") or "").strip():
        errors.append("model is required (the model string of the session that decided)")
    for k in C08_DISCRETIONARY:
        if ans.get(k):
            errors.append(f"{k} is not used under C08: the CLI sets the book from the forecasts (positions follow "
                          "each instrument's final forecast; only a named data failure excludes one)")
    if not _valid_sources(ans.get("sources_read")):         # C05 (a), kept
        errors.append("sources_read is empty: every daily review must research the main drivers across its universe ("
                      + ", ".join(RESEARCH_DRIVERS) + ") on the web before deciding and list what it read with URLs; "
                      "a review without it counts as failed")
    ferrs, forecasts = _check_forecasts(ans, wl)
    derrs, excluded = _check_c08_data_failures(ans, wl, marks_rows, today)
    errors += ferrs + derrs + _check_time_anchor(ans, now)  # C07 rule 3, kept
    if errors:
        return None, errors
    return c08_plan(records, marks_rows, today, forecasts, excluded, wl) | {"forecasts": forecasts}, []


def _apply_c08(ans: dict, plan: dict, records: list[dict], today: date, now: datetime, path, wl: list[dict]) -> dict:
    """Append a C08 daily review: the run, every forecast, the closing actions and the CLI's orders."""
    n0 = len(records)
    _ensure_account(records, today, path)
    model = str(ans["model"]).strip()
    by = {w["instrument"]: w for w in wl}
    pos = positions(records)
    run_rec = append(records, {
        "type": "run", "session": "daily_review", "date": today.isoformat(), "decided_at": now.isoformat(),
        "model": model, "session_url": ans.get("session_url"), "status": "ok", "c08": True,
        "market_summary": " ".join(str(ans.get("market_summary") or "").split()),
        "n_new": len(plan["opens"]), "n_reviews": len(plan["actions"]), "n_forecasts": len(plan["forecasts"]),
        "sources_read": (ans.get("sources_read") or [])[:40], "risk_after_pct": plan["risk_after_pct"],
        "book": {"targets": plan["targets"], "excluded": plan["excluded"],
                 "rule": (f"side of the final forecast; risk {C08_RISK_PER_POINT:g}% per point of |p - 50| (2% cap), "
                          f"scaled into {RISK_BUDGET[0]:g}-{RISK_BUDGET[1]:g}%; {C08_NO_TRADE_BAND:.0%} no-trade band")},
        **{k: ans[k] for k in ("data_failure", "time_anchor") if ans.get(k)}}, path)
    fids = {}
    n_fc = sum(1 for r in records if r["type"] == "forecast")
    for f in plan["forecasts"]:
        w = by[f["instrument"]]
        n_fc += 1
        fids[f["instrument"]] = f"JF{n_fc:04d}"
        append(records, {"type": "forecast", "forecast_id": fids[f["instrument"]], "instrument": f["instrument"],
                         "date": today.isoformat(), "decided_at": now.isoformat(), "model": model,
                         "run_seq": run_rec["seq"], "cluster": w["cluster"], "question": w["question"],
                         "yes_if": w["yes_if"],
                         "yes_position": w["yes_position"], "horizon_trading_days": w["horizon_trading_days"],
                         "resolution_source": w["resolution_source"], "p_initial": f["p_initial"],
                         "p_final": f["p_final"], "market_probability": f["market_probability"],
                         "market_basis": f["market_basis"], "market_source": f["market_source"],
                         "reasoning": f["reasoning"], "opposition": f["opposition"],
                         "excluded": f["instrument"] in plan["excluded"]}, path)
    for a in plan["actions"]:
        p = pos[a["id"]]
        base = {"position_id": a["id"], "date": today.isoformat(), "decided_at": now.isoformat(), "model": model,
                "set_by": "CLI (C08)", "reasoning": a["reasoning"], "run_seq": run_rec["seq"], "session": "daily_review",
                "c08": True}
        append(records, {"type": "review", "action": a["action"], **base}, path)
        if a["action"] == "close":
            if p["status"] == "pending":
                append(records, {"type": "cancel", "position_id": a["id"], "date": today.isoformat(),
                                 "reason": f"{a['close_reason']}: order withdrawn before it was filled"}, path)
            else:
                append(records, {"type": "close_request", "close_reason": a["close_reason"], **base}, path)
    fc = {f["instrument"]: f for f in plan["forecasts"]}
    for o in plan["opens"]:
        f, w = fc[o["instrument"]], by[o["instrument"]]
        long_ = o["direction"] == "long"
        p_side = f["p_final"] if long_ else 100 - f["p_final"]
        m_side = f["market_probability"] if long_ else 100 - f["market_probability"]
        pid = next_id(records)
        append(records, {
            "type": "open", "position_id": pid, "instrument": o["instrument"], "direction": o["direction"],
            "risk_pct": o["risk_pct"], "requested_risk_pct": o["target_risk_pct"], "stop": o["stop"],
            "horizon": (today + timedelta(days=MAX_HORIZON_DAYS)).isoformat(), "probability": float(p_side),
            "thesis": (f"{f['reasoning']} [C08 mechanical position: final forecast {f['p_final']}% that the answer to "
                       f"\"{w['question']}\" is YES, so the CLI holds the {o['direction']} side with "
                       f"{o['risk_pct']:.2f}% at risk.]"),
            "change_mind": ("Set by the CLI at each daily review (C08): the side follows the final forecast, the size "
                            f"is reset when the target moves by more than {C08_NO_TRADE_BAND:.0%}, and a named data "
                            "failure closes it. The stop and the 6-month horizon are backstops."),
            "sources": [], "sources_read": (ans.get("sources_read") or [])[:25], "model": model,
            "set_by": "CLI (C08)", "decided_at": now.isoformat(), "decision_date": today.isoformat(),
            "entry_rule": "next available first-hand daily mark dated on or after the decision date",
            "market_probability": float(m_side), "market_source": f["market_source"],
            "market_basis": f["market_basis"], "provisional_capacity": o["provisional_capacity"],
            "run_seq": run_rec["seq"], "session": "daily_review", "c08": True, "forecast_id": fids[o["instrument"]],
            "stop_rule": f"{w['stop']['distance']:g} {w['stop']['unit'].replace('_', ' ')} from the mark of "
                         f"{o['ref_date']} on the losing side",
            **({"replaces": o["replaces"]} if o["replaces"] else {}),
            **({"flips": o["flips"]} if o["flips"] else {}),
            **({"capacity_note": o["capacity_note"]} if o["capacity_note"] else {})}, path)
    return {"ok": True, "errors": [], "appended": [r["seq"] for r in records[n0:]],
            "opened": [r["position_id"] for r in records[n0:] if r["type"] == "open"],
            "forecasts": [fids[f["instrument"]] for f in plan["forecasts"]]}


def c08_rebalance_fills(records: list[dict], marks_rows: list[dict], today: date, path: Path | None,
                        reg: dict, ref: dict) -> list[str]:
    """A C08 resize (same side, ``replaces``) or side flip (``flips``) fills at one mark: the old position closes and
    the new one fills at the first first-hand daily mark dated on or after the review (and the old fill). A resize
    pays costs only on the notional actually traded: the part carried over is not sold and bought back. A stop hit
    before that mark is left to the usual processing (the old position closes at its stop, the order fills alone)."""
    log = []
    pos = positions(records)
    for pid, p in sorted(pos.items()):
        o = p["open"]
        old_id = o.get("replaces") or o.get("flips")
        old = pos.get(old_id) if old_id else None
        if p["status"] != "pending" or not old or old["status"] != "open" or not old.get("close_request"):
            continue
        inst = o["instrument"]
        if is_future(inst):
            continue
        k, ser = kind(inst, reg), series(marks_rows, inst)
        ed, dd = parse_date(old["fill"]["entry_date"]), parse_date(o["decision_date"])
        hit = next((x for x in ser if x[0] >= max(dd, ed) and x[0] <= today), None)
        if not hit:
            continue
        d, v, m = hit
        od = old["open"]["direction"]
        if any(PX.stop_hit(k, od, old["fill"]["entry_level"], stop_on(old, x[0]), x[1]) for x in ser if ed < x[0] < d):
            continue
        same = bool(o.get("replaces")) and od == o["direction"]
        old_nf = old["fill"]["notional_frac"]
        new_ok = PX.valid_stop(k, o["direction"], v, p["stop"])
        sz = size(inst, o["direction"], o["risk_pct"], v, p["stop"], reg, ref) if new_ok else None
        carried = min(old_nf, sz["notional_frac"]) if (same and sz) else 0.0
        exit_cost = 100 * (old_nf - carried) * (one_way_cost(inst, v) + old["fill"].get("impact_frac", 0.0))
        gross = pnl_at(old, v, reg)["gross_pct"]
        net = round(gross - _costs_pct(old) - exit_cost, 4)
        why = old["close_request"].get("close_reason") or ("C08 rebalance" if same else "C08 side flip")
        append(records, {"type": "close", "position_id": old_id, "date": d.isoformat(), "exit_level": v,
                         "reason": why, "mark_source": m.get("source"), "gross_pnl_pct": gross,
                         "exit_cost_pct": round(exit_cost, 5), "net_pnl_pct": net,
                         "outcome": "right" if gross > 0 else "wrong", "days_held": (d - ed).days,
                         "carried_notional_frac": carried, "replaced_by": pid}, path)
        log.append(f"{old_id} closed ({why}) at {v:g} on {d}: gross {gross:+.3f}%, net {net:+.3f}%")
        if not sz:
            append(records, {"type": "cancel", "position_id": pid, "date": d.isoformat(), "level": v,
                             "reason": f"the entry mark {v:g} ({d}) is already through the stop {p['stop']:g}; not opened"},
                   path)
            log.append(f"{pid} cancelled: entry mark through the stop")
            continue
        traded = sz["notional_frac"] - carried
        cost_frac = sz["one_way_cost"] + sz["impact_frac"]
        append(records, {"type": "fill", "position_id": pid, "entry_date": d.isoformat(), "entry_level": v,
                         "mark_source": m.get("source"), "mark_url": m.get("source_url"), "risk_pct": sz["risk_pct"],
                         "notional_frac": sz["notional_frac"], "notional_usd": sz["notional_usd"], "contracts": None,
                         "one_way_cost": sz["one_way_cost"], "impact_frac": sz["impact_frac"],
                         "cost_pct": round(100 * traded * cost_frac, 5), "traded_notional_frac": traded,
                         "carried_from": old_id if carried else None, "carried_notional_frac": carried,
                         "capacity": {k2: sz["capacity"][k2] for k2 in ("pct_adv", "adv_usd", "adv_status", "pct_limit",
                                                                        "position_limit", "impact_bp_trade", "flags")},
                         "capacity_note": sz["capacity_note"]}, path)
        log.append(f"{pid} filled {o['direction']} {inst} at {v:g} ({d}); carried {100 * carried:.2f}% of the account "
                   f"from {old_id}, traded {100 * traded:.2f}%")
        pos = positions(records)
    return log


def forecast_outcome(f: dict, marks_rows: list[dict], today: date) -> dict | None:
    """C08: how a forecast resolves (janus/watchlist.yaml): the base mark is the first first-hand daily mark dated on
    or after the forecast's date; the end mark the first dated on or after the 20th weekday after the base mark's
    date; YES when the end mark is strictly beyond the base mark in the ``yes_if`` direction. None until both exist."""
    ser = [x for x in series(marks_rows, f["instrument"]) if x[0] <= today]
    fd = parse_date(f["date"])
    base = next((x for x in ser if x[0] >= fd), None)
    if not base:
        return None
    target = add_weekdays(base[0], int(f.get("horizon_trading_days") or 20))
    end = next((x for x in ser if x[0] >= target), None)
    if not end:
        return {"base_date": base[0].isoformat(), "base_value": base[1], "target_date": target.isoformat()}
    yes = (end[1] < base[1]) if f["yes_if"] == "lower" else (end[1] > base[1])
    o = 1 if yes else 0
    def brier(p):
        return round((float(p) / 100.0 - o) ** 2, 6)
    return {"base_date": base[0].isoformat(), "base_value": base[1], "target_date": target.isoformat(),
            "end_date": end[0].isoformat(), "end_value": end[1], "outcome": o, "answer": "YES" if yes else "NO",
            "brier_final": brier(f["p_final"]), "brier_initial": brier(f["p_initial"]),
            "brier_market": brier(f["market_probability"]), "mark_source": end[2].get("source")}


def resolve_forecasts(records: list[dict], marks_rows: list[dict], today: date, path: Path | None = RECORDS) -> list[str]:
    """Append a ``forecast_resolution`` for every C08 forecast whose end mark has arrived (whether or not a position
    resulted). Run by ``mark`` (ledger-daily and every scripts/ledger_commit.sh write)."""
    done = {r["forecast_id"] for r in records if r["type"] == "forecast_resolution"}
    log = []
    for f in [r for r in records if r["type"] == "forecast" and r["forecast_id"] not in done]:
        res = forecast_outcome(f, marks_rows, today)
        if not res or "outcome" not in res:
            continue
        append(records, {"type": "forecast_resolution", "forecast_id": f["forecast_id"], "instrument": f["instrument"],
                         "forecast_date": f["date"], "date": today.isoformat(), "p_final": f["p_final"],
                         "p_initial": f["p_initial"], "market_probability": f["market_probability"], **res}, path)
        log.append(f"{f['forecast_id']} ({f['instrument']}, {f['date']}) resolved {res['answer']}: Brier "
                   f"{res['brier_final']:.4f} (p {f['p_final']}%)")
    return log


def forecast_rows(records: list[dict]) -> list[dict]:
    """Every C08 forecast with its resolution, if any."""
    res = {r["forecast_id"]: r for r in records if r["type"] == "forecast_resolution"}
    out = []
    for f in (r for r in records if r["type"] == "forecast"):
        r = res.get(f["forecast_id"], {})
        out.append({k: f.get(k) for k in ("forecast_id", "instrument", "date", "run_seq", "cluster", "question",
                                          "yes_if", "p_initial", "p_final", "market_probability", "market_basis",
                                          "reasoning", "excluded")}
                   | {"opposition_probability_view_wrong": (f.get("opposition") or {}).get("probability_view_wrong"),
                      "status": "resolved" if r else "open",
                      **{k: r.get(k) for k in ("base_date", "end_date", "base_value", "end_value", "outcome", "answer",
                                               "brier_final", "brier_initial", "brier_market")}})
    return out


def fund_calls(records: list[dict], clusters: dict[str, list[str]] | None = None) -> list[dict]:
    """The fund allocation rule's resolved calls (docs/fund/allocation.md; C08 rule 6 as amended by C09): one call per
    correlation cluster (janus/watchlist.yaml) per non-overlapping 20-trading-day window, so correlated forecasts do
    not count as independent calls.

    A cluster call is the set of that cluster's forecasts made in one daily review. Its window runs from the earliest
    base mark to the latest end mark of its forecasts, and it scores the mean of their Brier scores (Janus's p_final,
    p_initial, and the market's). Per cluster, in review order, the first review's call counts; the next one counted
    is the first whose earliest base mark is dated on or after the end of the last one counted. Which call counts
    depends only on dates, never on outcomes. A call resolves when all its forecasts have resolved; only resolved
    calls are listed, and a cluster's chain stops at a counted call that has not resolved yet. A forecast's cluster
    is the one recorded with it (the watchlist's, for forecasts recorded without one)."""
    clusters = clusters if clusters is not None else load_clusters()
    of = {i: c for c, ms in clusters.items() for i in ms}
    groups: dict[tuple, list[dict]] = {}
    for r in forecast_rows(records):
        c = r.get("cluster") or of.get(r["instrument"])
        if c:
            groups.setdefault((c, r.get("run_seq") or r["date"]), []).append(r)
    def mean(xs):
        return round(sum(xs) / len(xs), 6)
    out = []
    for c in dict.fromkeys(list(clusters) + [k[0] for k in groups]):
        last_end = None
        for (cc, _), ms in groups.items():
            if cc != c:
                continue
            if any(m["status"] != "resolved" for m in ms):
                break                                # its window is not known yet, nor any later call's
            base, end = min(m["base_date"] for m in ms), max(m["end_date"] for m in ms)
            if last_end is not None and base < last_end:
                continue                             # inside the last counted window
            out.append({"cluster": c, "date": ms[0]["date"], "run_seq": ms[0].get("run_seq"),
                        "forecast_ids": [m["forecast_id"] for m in ms], "instruments": [m["instrument"] for m in ms],
                        "base_date": base, "end_date": end,
                        "brier_final": mean([m["brier_final"] for m in ms]),
                        "brier_initial": mean([m["brier_initial"] for m in ms]),
                        "brier_market": mean([m["brier_market"] for m in ms])})
            last_end = end
    return sorted(out, key=lambda r: (r["end_date"], r["cluster"]))


def forecast_summary(records: list[dict]) -> dict:
    rows = forecast_rows(records)
    done = [r for r in rows if r["status"] == "resolved"]
    calls = fund_calls(records)
    def mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else None
    return {"n": len(rows), "n_resolved": len(done),
            "brier_final": mean([r["brier_final"] for r in done]),
            "brier_initial": mean([r["brier_initial"] for r in done]),
            "brier_market": mean([r["brier_market"] for r in done]),
            "fund_calls": len(calls), "fund_brier_final": mean([r["brier_final"] for r in calls]),
            "fund_brier_market": mean([r["brier_market"] for r in calls])}


def _public_error(e: str) -> str:
    """An error as written to the public failed-review record: details of futures errors are withheld, because
    their numbers can derive from licensed settlement prices (rule 7)."""
    futs = [c for c in UNIVERSE if is_future(c)]
    if "settlement" in e.lower() or any(f"({c})" in e or f" {c} " in f" {e} " for c in futs) or "contract" in e.lower():
        return e.split(":")[0] + ": rejected (details not recorded: futures errors can derive from licensed settlements)"
    return e


def review_status(records: list[dict], today: date) -> dict:
    """The latest daily review: failed if the CLI rejected it (a failed-review record, C06) or it recorded no
    sources_read (the research rule), missing if none since yesterday (UTC). The quick check flags either."""
    runs = [r for r in records if r.get("type") == "run" and r.get("session") == "daily_review"]
    if not runs:
        return {"last_date": None, "sources_read": 0, "status": "missing", "flags": ["no daily review recorded yet"]}
    last = runs[-1]
    d, n = parse_date(last["date"]), len(_valid_sources(last.get("sources_read")))
    flags = []
    rejected = last.get("status") == "failed"
    if rejected:
        why = "; ".join(last.get("errors") or [])
        flags.append(f"daily review {d} failed: rejected by the CLI ({why[:160] + ('...' if len(why) > 160 else '')})")
    elif n == 0:
        flags.append(f"daily review {d} failed: empty sources_read"
                     + (f" (before the {MANDATE_FROM} research rule)" if d < MANDATE_FROM else ""))
    if d < today - timedelta(days=1):
        flags.append(f"no daily review since {d}")
    status = "failed" if (rejected or n == 0) else ("missing" if d < today - timedelta(days=1) else "ok")
    return {"last_date": d.isoformat(), "sources_read": n, "status": status, "flags": flags}


def budget_status(records: list[dict], today: date) -> dict:
    """Risk at risk against the 3-10% budget; below 3% is flagged unless the latest daily review gave a current
    below_budget reason, or named deferred ideas on a non-trading day within the last 3 days. The reason is the
    latest recorded (not rejected) review's; an event-based reason expires at the end of the next trading day after
    the event (C06), and so does a pre-C06 reason dated by a correction (``BELOW_BUDGET_EXPIRY_CORRECTIONS``)."""
    risk = round(open_risk(positions(records)), 4)
    runs = [r for r in records if r.get("type") == "run" and r.get("session") == "daily_review"
            and r.get("status") != "failed"]
    last = runs[-1] if runs else {}
    out = {"risk_used_pct": risk, "budget_pct": list(RISK_BUDGET), "typical_positions": list(TYPICAL_POSITIONS),
           "flags": []}
    if risk >= RISK_BUDGET[0] - 1e-9:
        return out
    if last.get("c08"):
        # C08: the CLI sets the book inside 3-10%; below_budget is gone, and only a named data failure excludes an
        # instrument. Below 3% otherwise (stops between reviews, a capacity cut) is flagged until the next review.
        if last.get("data_failure") and float(last.get("risk_after_pct") or 0) < RISK_BUDGET[0] - 1e-9:
            names = ", ".join(sorted(_inst(d) for d in last["data_failure"] if isinstance(d, dict)))
            out["reason"] = f"C08 book: data failure named on {names} by the {last['date']} review"
        else:
            out["flags"].append(f"{risk:.2f}% at risk, below the {RISK_BUDGET[0]:g}% budget: the C08 book is reset "
                                "into 3-10% at the next daily review")
        return out
    bb, dd = last.get("below_budget"), last.get("deferred_ideas")
    until = parse_date((bb or {}).get("until")) if isinstance(bb, dict) else None
    expiry, why = reason_expiry(last)
    if until and expiry and expiry < until:
        until = expiry
    if until and until >= today:
        out["reason"] = f"below budget until {until}: {bb.get('condition')}"
    elif dd and last.get("date") and parse_date(last["date"]) >= today - timedelta(days=3):
        out["reason"] = f"{len(dd)} idea(s) deferred to the next trading day by the {last['date']} review"
    else:
        out["flags"].append(f"{risk:.2f}% at risk, below the {RISK_BUDGET[0]:g}% budget without a current specific reason"
                            + (f" (the {last.get('date')} review's reason expired at the end of {expiry}: {why})"
                               if expiry and until == expiry else ""))
    return out


def reason_expiry(run: dict) -> tuple[date | None, str | None]:
    """When a review's below_budget reason expires under C06: the end of the next trading day after its event, or the
    date a correction set for a reason recorded before C06."""
    corr = BELOW_BUDGET_EXPIRY_CORRECTIONS.get(run.get("hash") or "")
    if corr:
        return corr[1], f"C06, correction {corr[0]}"
    bb = run.get("below_budget")
    ed = parse_date(bb.get("event_date")) if isinstance(bb, dict) else None
    return (next_trading_day(ed), "C06, the next trading day after the event") if ed else (None, None)


def mandate_flags(records: list[dict], today: date) -> list[str]:
    return review_status(records, today)["flags"] + budget_status(records, today)["flags"]


MARKET_BASES = ("options", "prediction market", "futures", "other market", "none")
COIN_FLIP = 50.0


def _check_market(n: dict) -> list[str]:
    """Required on every new position (from 2026-11-06, before any Janus call resolved): the market's probability
    that the view is right, in % like ``probability``; its source; and its basis. Use the best market-implied
    figure available (option prices, a prediction market, futures pricing). Where none exists, basis "none" and
    exactly 50 (0.50, a coin flip) with a source saying so."""
    errs = []
    mp, src, basis = n.get("market_probability"), " ".join(str(n.get("market_source") or "").split()), \
        str(n.get("market_basis") or "").strip().lower()
    try:
        mpv = float(mp)
    except (TypeError, ValueError):
        return [f"market_probability is required: the market's probability (%, 0-100) that the view is right, from "
                f"option prices, a prediction market or futures pricing; where none exists use {COIN_FLIP:g} with "
                "market_basis 'none'"]
    if 0 < mpv <= 1 and mpv != COIN_FLIP:
        errs.append(f"market_probability {mpv:g} looks like a fraction: it is in % like probability (a coin flip is "
                    f"{COIN_FLIP:g}, not 0.50)")
    elif not (0 < mpv < 100):
        errs.append(f"market_probability {mpv:g} must be in (0, 100)")
    if basis not in MARKET_BASES:
        errs.append(f"market_basis must be one of {', '.join(MARKET_BASES)} (got {basis!r})")
    if not src:
        errs.append("market_source is required: where the market probability comes from (or why there is none)")
    if basis == "none" and abs(mpv - COIN_FLIP) > 1e-9:
        errs.append(f"market_basis 'none' means no market-implied probability exists: record exactly {COIN_FLIP:g} "
                    "(a coin flip)")
    return errs


def _validate_future(n: dict, inst: str, direction: str, risk: float, stop: float, hz: date | None, today: date,
                     ref: dict, settle_rows: list[dict] | None = None) -> tuple[dict, list[str]]:
    """Futures / options checks on top of the common rules. Needs the private settlements (the latest final
    settlement of the contract) for the stop side and the capacity check."""
    errs: list[str] = []
    srows = settle_rows if settle_rows is not None else settlement_rows()
    month = str(n.get("contract") or "").strip() or front_contract(inst, today)["month"]
    if len(month) != 7 or not ST.listed(inst, int(month[:4]), int(month[5:7])):
        return {}, [f"contract {month!r} must be a listed month YYYY-MM of {UNIVERSE[inst]['contract']}"]
    y, m = int(month[:4]), int(month[5:7])
    if ST.notice_date(inst, y, m) <= today + timedelta(days=JF.ROLL_BEFORE_NOTICE_DAYS):
        return {}, [f"contract {month} is within {JF.ROLL_BEFORE_NOTICE_DAYS} days of its notice date"]
    con = JF.contract(inst, month)
    ser = ST.series(srows, inst, month)
    if not ser:
        return {}, [f"no private settlement of {con['code']} in this session: the daily review needs em-macro-data "
                    "(EM_MACRO_DATA) to propose futures or options"]
    F = ser[-1][1]
    out = {"contract": con}
    if n.get("option"):
        spec, oerrs = JF.check_option(n, inst, month, F, today, hz, stop, JF.DV.cash_rate(ROOT, today))
        if oerrs:
            return {}, oerrs
        out["option"] = spec
        out["direction"] = "long" if JF.option_delta_up(spec, F, today) else "short"
        return out, errs
    s = JF.sign(direction)
    sr = s * (stop - F) / F
    if sr >= 0:
        return {}, [f"stop {stop:g} is not on the losing side of the latest {con['code']} settlement"]
    nf = (risk / 100.0) / abs(sr)
    cap = CAP.max_notional(inst, ref, F)
    if cap is not None and nf * ACCOUNT_USD > cap:
        errs.append(f"capacity: notional above 10% of daily volume or near the position limit; the most this stop "
                    f"allows is {risk * cap / (nf * ACCOUNT_USD):.2f}% at risk")
    return out, errs


def futures_needs(records: list[dict], today: date) -> dict[tuple[str, str], date]:
    """Contract months Janus's pending and open futures/options positions need, from the date each is needed."""
    out: dict[tuple[str, str], date] = {}
    for p in positions(records).values():
        inst = p["open"]["instrument"]
        if not is_future(inst) or p["status"] not in ("pending", "open"):
            continue
        if p["status"] == "pending":
            con = p["open"].get("contract") or front_contract(inst, parse_date(p["open"]["decision_date"]))
            out[(inst, con["month"])] = parse_date(p["open"]["decision_date"])
            continue
        for leg in JF.legs_of(p):
            out[(inst, leg["month"])] = min(out.get((inst, leg["month"]), leg["start"]), leg["start"])
        if not p["fill"].get("option"):
            nxt = front_contract(inst, today)
            out.setdefault((inst, nxt["month"]), today - timedelta(days=10))
    return out


def next_id(records: list[dict]) -> str:
    n = sum(1 for r in records if r["type"] == "open")
    return f"J{n + 1:03d}"


def _ensure_account(records: list[dict], today: date, path) -> None:
    if not account_start(records):
        append(records, {"type": "account_open", "date": today.isoformat(), "account_usd": ACCOUNT_USD, "index": 100.0,
                         "rules": {"max_risk_position_pct": MAX_RISK_POS, "max_risk_total_pct": MAX_RISK_TOTAL,
                                   "max_open": MAX_OPEN, "capacity_max_pct_adv": CAP.MAX_PCT_ADV,
                                   "stops": "tighten only", "entry": "next available first-hand daily mark"},
                         "universe": sorted(UNIVERSE), "dropped": [d["market"] for d in DROPPED],
                         "note": "Janus paper account opened: US$500,000,000, reported in % (index 100)."}, path)


def apply_proposal(ans: dict, now: datetime | None = None, path: Path | None = RECORDS,
                   marks_rows: list[dict] | None = None, dry_run: bool = False) -> dict:
    """Validate a session's proposal and, if it passes every rule, append its records (atomically: all or nothing).
    Fills happen later, at the next official daily mark (``process``)."""
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    today = now.date()
    marks_rows = marks_rows if marks_rows is not None else read_marks()
    records = load(path) if path else []
    v = verify(records)
    if not v["ok"]:
        return {"ok": False, "errors": [f"the Janus chain does not verify: {v['error']}"], "appended": []}
    c08 = ans.get("session") == "daily_review" and today >= C08_FROM
    plan = None
    if c08:                                         # config change C08: forced forecasts, the CLI sets the book
        wl = load_watchlist()
        plan, errors = validate_c08(ans, records, marks_rows, today, now, wl)
        reviews, new = [], []
    else:
        reviews, new, errors = validate(ans, records, marks_rows, today, now)
    if c08 and not errors:
        if dry_run:
            return {"ok": True, "errors": [], "dry_run": True, "appended": [], "risk_after_pct": plan["risk_after_pct"],
                    "would_close": [a["id"] for a in plan["actions"] if a["action"] == "close"],
                    "would_hold": [a["id"] for a in plan["actions"] if a["action"] == "hold"],
                    "would_open": [(o["instrument"], o["direction"], o["risk_pct"]) for o in plan["opens"]],
                    "targets": plan["targets"]}
        return _apply_c08(ans, plan, records, today, now, path, wl)
    if errors and not dry_run and ans.get("session") == "daily_review":
        # C06 rule 3 (closes Q004): a rejected daily review is recorded as failed, so the quick check flags it the
        # same day. Nothing else is appended; the session fixes every error and proposes again.
        rec = append(records, {"type": "run", "session": "daily_review", "date": today.isoformat(),
                               "decided_at": now.isoformat(), "model": str(ans.get("model") or "").strip(),
                               "session_url": ans.get("session_url"), "status": "failed", "n_new": 0, "n_reviews": 0,
                               "errors": [_public_error(e) for e in errors][:30],
                               "sources_read": _valid_sources(ans.get("sources_read"))[:40],
                               "proposal_sha256": hashlib.sha256(_canon(ans).encode()).hexdigest(),
                               **({"now_utc": str(ans["time_anchor"]["now_utc"])[:40]}
                                  if isinstance(ans.get("time_anchor"), dict) and ans["time_anchor"].get("now_utc")
                                  else {}),
                               **({"c08": True} if c08 else {}),
                               "note": "rejected by the CLI: nothing in the proposal was applied (C06)"}, path)
        return {"ok": False, "errors": errors, "dry_run": False, "appended": [rec["seq"]], "failed_record": rec["seq"],
                "would_open": [n["instrument"] for n in new], "would_review": [(r["id"], r["action"]) for r in reviews]}
    if errors or dry_run:
        return {"ok": not errors, "errors": errors, "dry_run": dry_run, "appended": [],
                "would_open": [n["instrument"] for n in new], "would_review": [(r["id"], r["action"]) for r in reviews]}
    n0 = len(records)
    _ensure_account(records, today, path)
    model, session = str(ans["model"]).strip(), ans["session"]
    run_rec = append(records, {"type": "run", "session": session, "date": today.isoformat(), "decided_at": now.isoformat(),
                               "model": model, "session_url": ans.get("session_url"), "status": "ok",
                               "market_summary": " ".join(str(ans.get("market_summary") or "").split()),
                               "n_new": len(new), "n_reviews": len(reviews),
                               "sources_read": (ans.get("sources_read") or [])[:40],
                               **({"risk_after_pct": round(open_risk(positions(records)) + sum(n["risk_pct"] for n in new)
                                                           - sum(positions(records)[r["id"]]["open"]["risk_pct"]
                                                                 for r in reviews if r["action"] == "close"), 4)}
                                  if session == "daily_review" else {}),
                               **{k: ans[k] for k in ("below_budget", "deferred_ideas", "market_holiday", "data_failure",
                                                       "time_anchor", "candidates")
                                  if ans.get(k)},
                               **({"flags": mandate_flags(records, today)} if session == "quick_check" else {})},
                     path)
    pos = positions(records)
    for r in reviews:
        p = pos[r["id"]]
        base = {"position_id": r["id"], "date": today.isoformat(), "decided_at": now.isoformat(), "model": model,
                "reasoning": " ".join(str(r.get("reasoning")).split()), "run_seq": run_rec["seq"], "session": session}
        append(records, {"type": "review", "action": r["action"], **base}, path)
        if r["action"] == "tighten_stop":
            append(records, {"type": "stop_change", "old_stop": p["stop"], "new_stop": r["new_stop"], **base}, path)
        elif r["action"] == "close":
            if p["status"] == "pending":
                append(records, {"type": "cancel", "position_id": r["id"], "date": today.isoformat(),
                                 "reason": "Janus closed the order before it was filled"}, path)
            else:
                append(records, {"type": "close_request", **base}, path)
    for n in new:
        pid = next_id(records)
        append(records, {"type": "open", "position_id": pid, "instrument": n["instrument"], "direction": n["direction"],
                         "risk_pct": n["risk_pct"], "requested_risk_pct": n["risk_pct"], "stop": n["stop"],
                         "horizon": n["horizon"], "probability": n["probability"],
                         "thesis": " ".join(str(n.get("thesis", "")).split()),
                         "change_mind": " ".join(str(n.get("change_mind", "")).split()),
                         "sources": n.get("sources") or [], "sources_read": (ans.get("sources_read") or [])[:25],
                         "model": model, "decided_at": now.isoformat(), "decision_date": today.isoformat(),
                         "entry_rule": ("first final exchange settlement of the contract dated on or after the decision date"
                                        if is_future(n["instrument"]) else
                                        "next available first-hand daily mark dated on or after the decision date"),
                         **({"contract": n["contract"]} if n.get("contract") else {}),
                         **({"option": n["option"]} if n.get("option") else {}),
                         "market_probability": float(n["market_probability"]),
                         "market_source": " ".join(str(n["market_source"]).split()),
                         "market_basis": str(n["market_basis"]).strip().lower(),
                         "provisional_capacity": n.get("provisional_capacity"), "run_seq": run_rec["seq"],
                         "session": session}, path)
        opp = n["opposition"]
        append(records, {"type": "opposition", "position_id": pid, "date": today.isoformat(),
                         "model": opp.get("model") or model, "decided_at": now.isoformat(),
                         "opposition": {k: opp.get(k) for k in ("case_against", "key_risks", "what_proves_it_wrong",
                                                                 "probability_view_wrong", "sources") if k in opp}}, path)
    if session == "daily_review" and not new:
        append(records, {"type": "no_trade", "date": today.isoformat(), "decided_at": now.isoformat(), "model": model,
                         "run_seq": run_rec["seq"], "reasoning": " ".join(str(ans["no_trade_reasoning"]).split())}, path)
    return {"ok": True, "errors": [], "appended": [r["seq"] for r in records[n0:]],
            "opened": [r["position_id"] for r in records[n0:] if r["type"] == "open"]}


def record_check(checked: list[str], result: str, model: str, now: datetime | None = None, path: Path | None = RECORDS,
                 session_url: str | None = None) -> dict:
    """A quick check that changed nothing (or a short note of what it saw): one line in the chain."""
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    records = load(path) if path else []
    v = verify(records)
    if not v["ok"]:
        raise ValueError(f"the Janus chain does not verify: {v['error']}")
    pos = positions(records)
    open_ids = sorted(pid for pid, p in pos.items() if p["status"] in ("open", "pending"))
    checked = sorted({c.strip() for c in checked if c.strip() and c.strip().lower() != "none"})
    unknown = [c for c in checked if c not in open_ids]
    if unknown:
        raise ValueError(f"not open positions: {', '.join(unknown)}")
    if checked != open_ids:
        raise ValueError(f"a check covers every open position: expected {', '.join(open_ids) or 'none'}")
    result = " ".join(str(result or "").split())
    if not result or len(result) > 240:
        raise ValueError("result is required, one line of at most 240 characters (e.g. 'no change')")
    if not str(model or "").strip():
        raise ValueError("model is required")
    _ensure_account(records, now.date(), path)
    flags = mandate_flags(records, now.date())          # added by the CLI: a quick check cannot leave them out
    return append(records, {"type": "check", "session": "quick_check", "time": now.isoformat(), "date": now.date().isoformat(),
                            "positions": checked, "result": result, "model": model.strip(), "session_url": session_url,
                            **({"flags": flags} if flags else {})}, path)


def context(marks_rows: list[dict] | None = None, today: date | None = None, fetch: bool = False) -> dict:
    """Everything a session needs to start (read-only): rules, open positions with entry, stop, latest mark, P&L and
    distance to stop, the universe with marks, the last check and the post-mortems that are due."""
    today = today or date.today()
    if fetch:
        from .marks import fetch_all, latest_marks
        reg_rows = [r for r in load_registry() if (r["instrument"] in UNIVERSE and not is_future(r["instrument"]))
                    or r["instrument"] in ("FR10Y", "DE10YBM")]
        fresh = fetch_all(reg_rows, today, previous=latest_marks())
        marks_rows = (marks_rows if marks_rows is not None else read_marks()) + [
            {k: v for k, v in m.items() if not k.startswith("_")} for m in fresh if m.get("value")]
    marks_rows = marks_rows if marks_rows is not None else read_marks()
    records = load()
    s = summarize(records, marks_rows, today)
    keep = ("id", "status", "instrument", "name", "direction", "risk_pct", "stop", "initial_stop", "horizon",
            "probability", "thesis", "change_mind", "mark", "mark_date", "net_pnl_pct", "distance_to_stop_pct_account",
            "unit", "estimate", "decided_at")
    from . import postmortem as PMm
    return {"today": today.isoformat(), "chain": s["chain"],
            "rules": {"max_risk_position_pct": MAX_RISK_POS, "max_risk_total_pct": MAX_RISK_TOTAL, "max_open": MAX_OPEN,
                      "capacity": "notional at most 10% of ADV and below 80% of any position limit",
                      "stops": "tighten only", "entry": "next available official daily mark, not the price now",
                      "thesis": "2-3 sentences",
                      "futures": ("futures by contract month (energy, COMEX metals, CBOT grains): optional 'contract' "
                                  "YYYY-MM (default the front contract by the 35-day rule); stop = a price of that "
                                  "contract; fill at the first final settlement on or after the decision date; prices "
                                  "are private (em-macro-data), never put them in a public file"),
                      "options": ("defined risk only: 'option': {legs, expiry, iv_pct, iv_source or 'estimate'} - a long "
                                  "call or put, or a vertical; risk_pct = maximum loss; stop = an underlying level; "
                                  "horizon on or before expiry; valued with Black-76 (model estimate)"),
                      "market_probability": ("required on every new position: the market's probability (%, "
                                             "0-100) that the view is right, with market_source and market_basis "
                                             "(options, prediction market, futures, other market, or none = exactly "
                                             "50, a coin flip); the fund's Janus rule compares Brier scores with it "
                                             "(docs/fund/allocation.md)"),
                      "required": ["instrument", "direction", "risk_pct", "stop", "horizon",
                                                              "probability", "market_probability", "market_source", "market_basis",
                                                              "thesis", "change_mind", "sources",
                                                              "opposition.case_against"]},
            "mandate": {"from": MANDATE_FROM.isoformat(),
                        "research": ("required: every daily review researches the main drivers across the universe ("
                                     + ", ".join(RESEARCH_DRIVERS) + ") on the web before deciding and records them in "
                                     "sources_read; a review without it is rejected (counts as failed)"),
                        "risk_budget": (f"normally {TYPICAL_POSITIONS[0]}-{TYPICAL_POSITIONS[1]} positions and "
                                        f"{RISK_BUDGET[0]:g}-{RISK_BUDGET[1]:g}% of the account at risk, best ideas even at "
                                        "modest conviction (e.g. 55%); size scales with conviction and edge over the "
                                        f"market probability (a small edge: {SMALL_EDGE_RISK[0]:g}-{SMALL_EDGE_RISK[1]:g}% "
                                        f"at risk); below {RISK_BUDGET[0]:g}% only with below_budget {{condition, until, "
                                        "reasoning}} naming a specific event or condition; weekend and holiday reviews "
                                        "may defer entries with deferred_ideas"),
                        "c06": {"from": C06_FROM.isoformat(),
                                "min_positions": (f"at least {MIN_POSITIONS} open positions at all times: below_budget "
                                                  "may let risk fall below 3%, never the count; fewer only with "
                                                  "data_failure [{instrument, mark, last_mark (date or 'none')}], "
                                                  f"stale = {DATA_STALE_WEEKDAYS}+ weekdays without a mark, and only "
                                                  "for the instruments affected (other instruments with current marks "
                                                  "must be used)"),
                                "event_reason": ("an event-based below_budget gives event_date (YYYY-MM-DD) and "
                                                 "calendar_url, the official calendar that dates the event, also "
                                                 "listed in sources_read; it expires at the end of the next trading "
                                                 "day after the event (until no later)"),
                                "official_calendars": list(OFFICIAL_CALENDAR_HOSTS),
                                "rejected_review": ("a rejected daily review appends a failed-review record (exit 3) "
                                                    "that the quick check flags; --dry-run writes nothing")},
                        "c07": {"from": C07_FROM.isoformat(),
                                "no_coin_flips": ("no opened position or deferred idea may state probability 50: state "
                                                  "the side you favour, or do not open it"),
                                "wider_search": (f"when the C06 minimum binds (the book held fewer than "
                                                 f"{MIN_POSITIONS} and the review brings it to exactly {MIN_POSITIONS}), "
                                                 f"candidates lists at least {MIN_CANDIDATES} instruments across at "
                                                 f"least {MIN_CANDIDATE_CLASSES} asset classes (rates, fx, "
                                                 "commodities), each {instrument, direction, probability, "
                                                 "market_probability, outcome: opened|deferred|not_opened, "
                                                 "opposition: kept|dropped|none, reason}, including every opened "
                                                 "position; a candidate dropped after The Opposition is reopened "
                                                 "only with reopen_reason naming why each not-opened candidate is "
                                                 "not better"),
                                "time_anchor": ("every daily review gives time_anchor {now_utc: its current UTC time "
                                                "(at most 3 hours old when proposed), events: [{event, time_utc (or "
                                                "date when not on the review's UTC date), occurred}]} covering every "
                                                "date and scheduled event (CPI, payrolls, FOMC, ...) named in a "
                                                "reason, thesis or the market summary; an event dated in the future "
                                                "cannot be described as released"),
                                "deferrals": ("a deferred idea counts toward the 2-position minimum only if its "
                                              "market is closed on the review date (every market on a weekend; FX "
                                              "only on 1 Jan and 25 Dec; any other market on a weekday with "
                                              "market_closed {holiday, calendar_url} from an official or exchange "
                                              "calendar listed in sources_read), and must open at the next session "
                                              "(carried forward in deferred_ideas while its market stays closed)"),
                                "market_calendars": list(MARKET_CALENDAR_HOSTS)},
                        "c08": {"from": C08_FROM.isoformat(),
                                "forecasts": ("every daily review gives forecasts: one per watchlist instrument "
                                              "(janus/watchlist.yaml, below), each {instrument, p_initial (before The "
                                              "Opposition), p_final, reasoning, opposition {case_against, "
                                              "probability_view_wrong, model}}; probabilities are whole numbers from "
                                              "1 to 99, never 50, that the question resolves YES; market_probability "
                                              "/ market_basis / market_source optional (default 50, basis none). "
                                              "Every forecast is logged and resolved with a Brier score"),
                                "book": (f"the CLI sets the book: each instrument on the side of its final forecast "
                                         f"(YES = long), risk {C08_RISK_PER_POINT:g}% per point of |p - 50| (at most "
                                         f"{MAX_RISK_POS:g}% each), scaled into {RISK_BUDGET[0]:g}-{RISK_BUDGET[1]:g}% "
                                         f"when outside it; rebalanced at each daily review with a "
                                         f"{C08_NO_TRADE_BAND:.0%} no-trade band; mechanical stops from the watchlist"),
                                "exclusions": ("only data_failure [{instrument, mark, last_mark}] (verified: the mark "
                                               "is stale) excludes an instrument from the book; it is still forecast"),
                                "not_used": list(C08_DISCRETIONARY),
                                "opposition": "advisory: it never vetoes a forecast",
                                "kept": ("sources_read (C05 a), time_anchor (C07 rule 3, now also covering every "
                                         "forecast's reasoning), failed-review records and exit 3 (C06 rule 3), "
                                         "licensed data never in public error text"),
                                "superseded": ("C05 (b) sizing table, below_budget and weekend deferrals; C06 rules 1 "
                                               "and 2; C07 rules 1, 2 and 4; discretionary new positions and reviews "
                                               "(a quick check cannot close or tighten a C08 position)"),
                                "fund_resolved_call": ("one call per correlation cluster (janus/watchlist.yaml: "
                                                       "G10 yields, USD vs G10 FX, EM FX, gold) per non-overlapping "
                                                       "20-trading-day window, scored on the mean Brier of its "
                                                       "forecasts (C09; docs/fund/allocation.md)")}},
            "watchlist": _watchlist_context(marks_rows, today),
            "forecasts_open": [r for r in forecast_rows(records) if r["status"] == "open"][-40:],
            "forecast_summary": forecast_summary(records),
            "daily_review_status": review_status(records, today), "risk_budget_status": budget_status(records, today),
            "flags": mandate_flags(records, today),
            "risk_used_pct": s["risk_used_pct"], "n_open": s["n_open"],
            "open": [{k: p.get(k) for k in keep} | {"entry": (p.get("fill") or {}).get("entry_level"),
                                                     "entry_date": (p.get("fill") or {}).get("entry_date")} for p in s["open"]],
            "universe": market_snapshot(marks_rows, today), "last_check": s["last_check"],
            "postmortems_due": [f"{c['book']}-{c['id']}" for c in PMm.due()]}


def _watchlist_context(marks_rows: list[dict], today: date) -> list[dict]:
    out = []
    for w in load_watchlist():
        ser = series(marks_rows, w["instrument"], actable_only=False)
        out.append({k: w[k] for k in ("instrument", "name", "question", "yes_if", "yes_position", "horizon_trading_days",
                                      "resolution_source", "stop")}
                   | {"mark": ser[-1][1] if ser else None, "mark_date": ser[-1][0].isoformat() if ser else None})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["context", "propose", "check", "mark", "verify", "status"])
    ap.add_argument("--file", help="propose: the proposal JSON (outside the repository, e.g. /tmp/proposal.json)")
    ap.add_argument("--dry-run", action="store_true", help="propose: validate only")
    ap.add_argument("--positions", default="", help="check: comma-separated open ids checked, or 'none'")
    ap.add_argument("--result", default="", help="check: one line, e.g. 'no change'")
    ap.add_argument("--model", default="", help="check: the session's model string")
    ap.add_argument("--session-url", default=None)
    ap.add_argument("--fetch", action="store_true", help="context: fetch fresh official marks (not written)")
    ap.add_argument("--today", default=None)
    a = ap.parse_args(argv)
    today = parse_date(a.today) if a.today else date.today()
    ST.set_read_only()          # Janus only reads the private store: every write from this process is refused
    if a.cmd in ("context", "propose", "mark"):
        # futures settlements: an existing private store, or a read-only clone (ledger/settlements.py)
        _store, status = ST.ensure_read_only_store()
        print(f"settlements: {status}", file=sys.stderr)
    if a.cmd == "verify":
        v = verify(load())
        print(json.dumps(v))
        return 0 if v["ok"] else 1
    if a.cmd == "context":
        print(json.dumps(context(today=today, fetch=a.fetch), indent=1, default=str))
        return 0
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
        print(json.dumps({k: s[k] for k in ("risk_used_pct", "n_open", "n_closed", "hit_rate", "brier", "calls_needed",
                                            "last_check")}, default=str))
        for p in s["positions"]:
            print(p["id"], p["status"], p["direction"], p["instrument"], p["risk_pct"], p.get("net_pnl_pct"))
        return 0
    if a.cmd == "check":
        try:
            rec = record_check(a.positions.split(","), a.result, a.model, session_url=a.session_url)
        except ValueError as e:
            print(f"REJECTED: {e}", file=sys.stderr)
            return 1
        print(json.dumps({k: rec[k] for k in ("seq", "time", "positions", "result")}))
        return 0
    if not a.file:
        print("propose needs --file", file=sys.stderr)
        return 2
    try:
        ans = json.loads(Path(a.file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"REJECTED: cannot read the proposal: {e}", file=sys.stderr)
        return 1
    res = apply_proposal(ans, dry_run=a.dry_run)
    print(json.dumps(res, indent=1, default=str))
    if not res["ok"]:
        if res.get("failed_record"):
            # exit 3: rejected, and the failed-review record (C06) was appended; scripts/ledger_commit.sh commits it
            print(f"REJECTED: nothing in the proposal was applied; failed-review record {res['failed_record']} was "
                  "appended (C06). Fix every error above and propose again.", file=sys.stderr)
            return 3
        print("REJECTED: nothing was appended. Fix every error above and propose again.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
