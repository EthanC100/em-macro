"""Column layout of the ledger CSV files and the validation rules shared by the
issue-intake workflow and the build.

Validation rules (from the programme brief):
  * the stop must contain a numeric price or yield level;
  * a position (Buy or Sell) must risk at most 2% of the account;
  * every decision states the probability its view is right; event-bet sizing is half of
    quarter-Kelly on that probability (even odds unless stated), reported alongside;
  * all dates must parse (YYYY-MM-DD, or a day-month-year that is unambiguous).
"""
from __future__ import annotations

import re
from datetime import date, datetime

DECISION_COLUMNS = [
    "id", "date", "country", "instrument", "action", "size_pct", "position_type", "probability",
    "claude_probability", "horizon", "entry_trigger", "stop", "thesis", "key_factors",
    "change_mind", "vs_consensus", "entry_level", "status", "outcome", "exit_price",
    "pnl_pct", "resolved_date", "resolution_note", "issue", "logged_at",
]
POSITION_TYPES = ("continuous", "event")
FORECAST_COLUMNS = [
    "id", "date", "question", "country", "my_prob", "market_prob", "market_source",
    "claude_prob", "resolution_date", "resolution_source", "status", "outcome", "result", "resolved_date",
    "issue", "logged_at",
]
AUTO_PREFIX = "Auto-resolved"      # resolution_note / result of an automatic resolution starts with this
ACTIONS = ("Buy", "Sell", "No trade")
REPORT_TYPES = ("daily briefing", "weekly review", "monthly notebook", "investor letter", "research", "screener", "other")
DECISION_OUTCOMES = ("right", "wrong", "no trade", "scratched")
FORECAST_OUTCOMES = ("yes", "no", "void")
MAX_RISK_PCT = 2.0
KELLY_FRACTION = 0.5 * 0.25      # half of quarter-Kelly
EVENT_SIZE_TOLERANCE = 0.05      # percentage points of account: an event bet must match its Kelly size this closely


def position_type(d: dict) -> str:
    """'event' or 'continuous' (the default for a Buy or Sell; blank for a no-trade)."""
    t = str(d.get("position_type") or "").strip().lower()
    if t.startswith("event"):
        return "event"
    return "continuous" if d.get("action") in ("Buy", "Sell") else ""

_NUM = re.compile(r"(?<![A-Za-z\d.])[-+]?\d+(?:[.,]\d+)?(?P<suffix>[A-Za-z%]*)")
_TENOR_SUFFIX = re.compile(r"^(y|yr|yrs|m|mo|mth|d|w|wk|s|h|x)$", re.I)   # 10y, 3m, 2s (not bp, %)
_DATE_FORMATS = ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y",
                 "%B %d %Y", "%b %d %Y", "%B %d, %Y", "%b %d, %Y", "%Y/%m/%d")


def parse_date(text: str | None) -> date | None:
    """Parse a date in any of the accepted forms; None if it does not parse."""
    if not text:
        return None
    s = str(text).strip().replace("–", "-")
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_number(text: str | None) -> float | None:
    """First price-like number in a string ('1.5%', '115bp', '5.70') or None.
    Tenor tokens such as '10y', '3m' or '2s10s' are skipped."""
    if text is None:
        return None
    for m in _NUM.finditer(str(text).replace("\u2212", "-")):
        suffix = m.group("suffix") or ""
        if _TENOR_SUFFIX.match(suffix):
            continue
        num = m.group(0)[: len(m.group(0)) - len(suffix)]
        return float(num.replace(",", "."))
    return None


def parse_probability(text: str | None) -> float | None:
    """Probability as a percentage 0-100 from '65', '65%', '0.65'."""
    v = parse_number(text)
    if v is None:
        return None
    if 0 < v <= 1 and "%" not in str(text):
        v *= 100
    if 0 <= v <= 100:
        return v
    return None


def kelly_size_pct(p_pct: float, odds: float = 1.0) -> float:
    """Half of quarter-Kelly as % of account for probability p (in %) at odds b."""
    p = p_pct / 100.0
    f = p - (1 - p) / odds
    return round(max(0.0, KELLY_FRACTION * f) * 100, 3)


def validate_decision(d: dict) -> tuple[list[str], list[str]]:
    """Return (errors, notes) for a decision record with the DECISION_COLUMNS keys."""
    errors: list[str] = []
    notes: list[str] = []
    for key, label in (("date", "Date"), ("horizon", "Horizon")):
        if parse_date(d.get(key)) is None:
            errors.append(f"{label} must be a date (YYYY-MM-DD); got {d.get(key)!r}.")
    if d.get("action") not in ACTIONS:
        errors.append(f"Action must be one of {', '.join(ACTIONS)}; got {d.get('action')!r}.")
    for key in ("country", "instrument", "thesis"):
        if not str(d.get(key) or "").strip():
            errors.append(f"{key.capitalize()} is required.")
    size = parse_number(d.get("size_pct"))
    if size is None:
        errors.append("Size must be a number (% of account at risk), e.g. 1.0.")
    prob = parse_probability(d.get("probability"))
    if prob is None:
        errors.append("Probability my view is right must be a percentage between 0 and 100.")
    if parse_number(d.get("stop")) is None:
        errors.append("Stop / exit if wrong must contain a numeric price or yield level "
                      "(for example '5.70' or '115bp').")
    ptype = position_type(d)
    if d.get("action") in ("Buy", "Sell"):
        if size is not None and size <= 0:
            errors.append("A Buy or Sell decision needs a positive size; use 'No trade' for 0%.")
        if ptype == "event":
            if prob is not None and size is not None and size > 0:
                req = kelly_size_pct(prob)
                if req <= 0:
                    errors.append(f"An event bet at {prob:g}% has no edge at even odds (half of quarter-Kelly "
                                  "gives 0%); state a probability above 50% or log it as No trade.")
                elif abs(size - req) > EVENT_SIZE_TOLERANCE:
                    errors.append(f"An event bet must be sized at half of quarter-Kelly on its probability: "
                                  f"{req:g}% of account at {prob:g}% (even odds); size is {size:g}%.")
                else:
                    notes.append(f"Event bet sized at half of quarter-Kelly: {req:g}% of account at {prob:g}%.")
        else:
            if size is not None and size > MAX_RISK_PCT:
                errors.append(f"A continuous position may risk at most {MAX_RISK_PCT:g}% of the account; "
                              f"size is {size:g}%.")
            if prob is not None:
                cap = kelly_size_pct(prob)
                notes.append(f"Continuous position (cap {MAX_RISK_PCT:g}%). For reference, an event bet at {prob:g}% "
                             f"would be sized at {cap:g}% (half of quarter-Kelly, even odds).")
    elif d.get("action") == "No trade" and size not in (None, 0):
        errors.append("A 'No trade' decision must have size 0.")
    claude = d.get("claude_probability")
    if claude and parse_probability(claude) is None:
        errors.append("Claude probability must be a percentage between 0 and 100 if given.")
    return errors, notes


def validate_forecast(f: dict, require_market: bool = True) -> tuple[list[str], list[str]]:
    """Return (errors, notes) for a forecast. require_market=False (a pasted FORECAST block, which has only
    Question, Probability and Resolves by) makes market probability, market source and resolution source
    optional; a market probability that is given must still be a percentage."""
    errors: list[str] = []
    notes: list[str] = []
    if not str(f.get("question") or "").strip():
        errors.append("Question is required.")
    if parse_probability(f.get("my_prob")) is None:
        errors.append("My probability must be a percentage between 0 and 100.")
    if require_market:
        if parse_probability(f.get("market_prob")) is None:
            errors.append("Market probability must be a percentage between 0 and 100.")
        if not str(f.get("market_source") or "").strip():
            errors.append("Market source is required (where the market probability comes from).")
        if not str(f.get("resolution_source") or "").strip():
            errors.append("Resolution source is required: what settles the question, for example 'AP race call', "
                          "'BCB official statement' or 'ECB press release'.")
    elif f.get("market_prob") and parse_probability(f.get("market_prob")) is None:
        errors.append("Market probability must be a percentage between 0 and 100 if given.")
    c = f.get("claude_prob")
    if c and parse_probability(c) is None:
        errors.append("Claude probability must be a percentage between 0 and 100 if given.")
    if parse_date(f.get("resolution_date")) is None:
        errors.append(f"Resolution date must be a date (YYYY-MM-DD); got {f.get('resolution_date')!r}.")
    if f.get("date") and parse_date(f.get("date")) is None:
        errors.append(f"Date must be a date (YYYY-MM-DD); got {f.get('date')!r}.")
    return errors, notes


def next_id(existing: list[str], prefix: str) -> str:
    n = 0
    for e in existing:
        if e and e.startswith(prefix) and e[len(prefix):].isdigit():
            n = max(n, int(e[len(prefix):]))
    return f"{prefix}{n + 1:03d}"
