"""Daily auto-resolver: close decisions and settle forecasts from the marks and official data.

    python -m ledger.resolve --out /tmp/resolve.json [--today 2026-11-10] [--dry-run]

Decisions (data/ledger/decisions.csv), for every open row whose instrument is in the registry:
  * stop hit: the first mark dated on or after the decision date that crosses the stop level
    (side from the entry level, else from the wording: "above", "rises", "widens" / "below",
    "falls", "tightens") closes the row as wrong at that mark; P&L from entry, stop and size, or
    minus the size at risk when there is no entry level;
  * horizon passed: the latest mark closes the row; a position is right / wrong / scratched by
    the sign of its P&L (a [RESOLVE?] issue when it cannot be computed); a no-trade whose stop
    was never hit is right.
Forecasts (data/ledger/forecasts.csv), for every open row past its resolution date:
  * mechanical, a central-bank decision: BIS daily policy rates (WS_CBPOL), no API;
  * mechanical, a price, yield or spread level: the registry's marks, no API;
  * event: settled by the forecast resolver session (a Claude Code scheduled task, docs/ledger/forecast_resolver.md:
    ``python -m ledger.resolve events`` lists them blind, ``settle-events --file`` settles them, accepted only with
    two independent sources). No API call is made here. If no session has settled one ``session_resolve_grace_days``
    after its resolution date, a [RESOLVE?] issue is opened with the session's last finding;
  * anything else, or a question the official data cannot settle yet, gets a "[RESOLVE?] <id>"
    issue (written to the --out JSON for the workflow to open) and is tried again the next day.
Every automatic resolution is written in the Resolve form's format (status, outcome, exit /
result with the source links, resolved date) and prefixed "Auto-resolved" so that a Resolve form
submitted later overrides it. Scores (Brier for me, Claude and the market; P&L) follow from the
same fields, as for a manual resolution.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .intake import read_rows, write_rows
from .marks import (CONFIG, http_get, latest_marks, load_registry, mark_can_act, mark_is_current,
                    match_instrument, read_marks)
from .independence import independent_sources
from .schema import (AUTO_PREFIX, DECISION_COLUMNS, FORECAST_COLUMNS, entry_number, parse_date, parse_number,
                     stop_level)
from .scoring import pnl_at_level, score_decision, score_forecast

ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/ethanc100/em-macro"
AUTO_LOG = ROOT / "data/ledger/automation_log.csv"
AUTO_LOG_COLUMNS = ["date", "kind", "id", "action", "detail"]

ABOVE_WORDS = r"above|over|rises?|rising|widens?|widening|wider|higher|greater|more than|exceeds?|breaks? above|closes? above|at least|at or above|up through|hikes?"
BELOW_WORDS = r"below|under|falls?|falling|drops?|tightens?|tightening|tighter|narrower|lower|less than|breaks? below|closes? below|at most|at or below|down through"

# central banks for mechanical rate questions -> BIS WS_CBPOL area code
CENTRAL_BANKS = [
    (r"\b(ecb|european central bank|governing council)\b", "XM", "ECB"),
    (r"\b(fed|fomc|federal reserve|fed funds)\b", "US", "Federal Reserve"),
    (r"\b(bcb|copom|banco central do brasil|selic)\b", "BR", "BCB (Copom)"),
    (r"\b(banxico|banco de m[eé]xico)\b", "MX", "Banxico"),
    (r"\b(sarb|south african reserve bank|repo rate)\b", "ZA", "SARB"),
    (r"\b(cbrt|tcmb|turkish central bank|central bank of turkey|t[uü]rkiye)\b", "TR", "CBRT"),
    (r"\b(bank indonesia|bi[- ]rate|bi7drr)\b", "ID", "Bank Indonesia"),
    (r"\b(nbp|rpp|national bank of poland|narodowy bank polski)\b", "PL", "NBP"),
    (r"\b(boe|bank of england|mpc)\b", "GB", "Bank of England"),
    (r"\b(banrep|banco de la rep[uú]blica)\b", "CO", "BanRep"),
    (r"\b(bcch|banco central de chile)\b", "CL", "BCCh"),
]
RATE_VERBS = r"\b(cut|cuts|cutting|lower|lowers|ease|eases|reduce|reduces|hike|hikes|raise|raises|tighten|tightens|increase|increases|hold|holds|unchanged|keep|keeps|pause|pauses|on hold)\b"
MONTHS = {m.lower(): i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                               "August", "September", "October", "November", "December"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# ----------------------------------------------------------------------------- decisions
def stop_rule(d: dict) -> tuple[float | None, str | None]:
    """(stop level, side): side 'below' means the stop is hit when the mark is at or below the
    level, 'above' when at or above it. From the entry level when there is one, else the wording."""
    level = stop_level(d.get("stop"))
    if level is None:
        return None, None
    entry = entry_number(d.get("entry_level"))
    if entry is not None and entry != level:
        return level, "below" if level < entry else "above"
    text = (d.get("stop") or "").lower()
    a, b = re.search(ABOVE_WORDS, text), re.search(BELOW_WORDS, text)
    if a and (not b or a.start() < b.start()):
        return level, "above"
    if b:
        return level, "below"
    return level, None


def stop_hit(d: dict, value: float) -> bool | None:
    level, side = stop_rule(d)
    if level is None or side is None or value is None:
        return None
    return value <= level if side == "below" else value >= level


def _unit_str(v: float, unit: str) -> str:
    if unit == "bp":
        return f"{v:g}bp"
    if unit and unit.startswith("%"):
        return f"{v:g}%"
    return f"{v:g} {unit}".strip()


def close_decision(d: dict, mark: dict, today: date, reason: str, outcome: str, pnl: float | None, extra: str = "") -> None:
    v = float(mark["value"])
    d["status"] = "resolved"
    d["outcome"] = outcome
    d["exit_price"] = f"{v:g}"
    d["pnl_pct"] = f"{pnl:g}" if pnl is not None else ""
    d["resolved_date"] = today.isoformat()
    src = f"{mark.get('source', '')} {mark.get('source_url', '')}".strip()
    d["resolution_note"] = (f"{AUTO_PREFIX} ({reason}) on {today.isoformat()}: exit {_unit_str(v, mark.get('unit', ''))} "
                            f"marked {mark.get('date')} ({mark.get('frequency', 'daily')}) from {src}."
                            + (f" {extra}" if extra else "")
                            + " A Resolve form with this id overrides this.")


def process_decisions(rows: list[dict], marks_rows: list[dict], registry: list[dict], today: date,
                      root: Path | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """Close open decisions in place. Returns (changed rows, issues, log lines)."""
    changed, issues, log = [], [], []
    from .derivs import load_terms
    derivs = load_terms(ROOT if root is None else root)
    for d in rows:
        if (d.get("status") or "open").strip().lower() != "open":
            continue
        if d.get("id") in derivs:
            continue          # futures/options: marked and closed on contract-month settlements by ledger.derivs mark
        horizon = parse_date(d.get("horizon"))
        dd = parse_date(d.get("date"))
        horizon_passed = bool(horizon and today >= horizon)
        reg = match_instrument(d.get("instrument", ""), registry)
        if reg is None:
            if horizon_passed:
                issues.append(resolve_issue(d["id"], "decision", d,
                                            f"The horizon {d.get('horizon')} has passed but the instrument "
                                            f"\"{d.get('instrument')}\" matches nothing in data/ledger/instruments.csv, "
                                            "so there is no mark to close it with. Add an alias to the registry or resolve by hand."))
            continue
        # only daily, fresh, first-hand marks may stop or close a position (mark_can_act): a monthly average
        # (dated at its month end) or a carried-forward mark never acts (D001 / FR-DE, 2026-11-06)
        current = [m for m in marks_rows if m.get("instrument") == reg["instrument"] and m.get("value")
                   and mark_is_current(d, m) and parse_date(m["date"]) <= today]
        marks = sorted((m for m in current if mark_can_act(m)), key=lambda m: m["date"])
        skipped = [m for m in current if m not in marks]
        if skipped:
            log.append(f"{d['id']}: {len(skipped)} mark(s) of {reg['instrument']} ignored for stops and closes "
                       f"(monthly average, stale or carried forward; latest {skipped[-1].get('date')} "
                       f"{skipped[-1].get('frequency')})")
        if not marks:
            if horizon_passed:
                issues.append(resolve_issue(d["id"], "decision", d,
                                            f"The horizon {d.get('horizon')} has passed but no mark of {reg['instrument']} "
                                            f"dated on or after the decision date exists yet (source frequency: {reg.get('frequency')})."))
            continue
        is_position = d.get("action") in ("Buy", "Sell")
        size = parse_number(d.get("size_pct"))
        hit = next((m for m in marks if stop_hit(d, float(m["value"]))), None)
        if hit is not None:
            pnl = pnl_at_level(d, float(hit["value"]))
            extra = ""
            if is_position and pnl is None and size is not None:
                pnl, extra = round(-abs(size), 3), "P&L set to the size at risk (no entry level recorded)."
            close_decision(d, hit, today, "stop hit", "wrong", pnl if is_position else None, extra)
            changed.append(d)
            log.append(f"{d['id']} closed: stop hit at {hit['value']} on {hit['date']} ({reg['instrument']}); outcome wrong"
                       + (f", P&L {pnl:+g}%" if pnl is not None else ""))
            continue
        if not horizon_passed:
            continue
        last = marks[-1]
        if is_position:
            pnl = pnl_at_level(d, float(last["value"]))
            if pnl is None:
                issues.append(resolve_issue(d["id"], "decision", d,
                                            f"The horizon {d.get('horizon')} has passed. Latest mark of {reg['instrument']}: "
                                            f"{last['value']} {last.get('unit', '')} on {last['date']} ({last.get('source')}), but the P&L "
                                            "cannot be computed because the record has no numeric entry level. Resolve with the "
                                            "form (enter the P&L), or add entry_level to the CSV and the resolver closes it tomorrow."))
                continue
            outcome = "scratched" if abs(pnl) < 0.01 else ("right" if pnl > 0 else "wrong")
            close_decision(d, last, today, "horizon reached", outcome, pnl)
        else:
            close_decision(d, last, today, "horizon reached", "right", None,
                           "The stop level was never crossed before the horizon, so the no-trade view held.")
        changed.append(d)
        log.append(f"{d['id']} closed: horizon {d.get('horizon')} reached, exit {last['value']} on {last['date']}; outcome {d['outcome']}"
                   + (f", P&L {d['pnl_pct']}%" if d.get("pnl_pct") else ""))
    return changed, issues, log


# ----------------------------------------------------------------------------- forecasts
def detect_central_bank(text: str):
    t = text.lower()
    for pat, area, name in CENTRAL_BANKS:
        if re.search(pat, t):
            return area, name
    return None


def parse_rate_question(text: str) -> dict | None:
    """'Does the ECB cut in December 2026?' -> {area, bank, verb, size_bp, month}."""
    cb = detect_central_bank(text)
    if not cb:
        return None
    t = text.lower()
    m = re.search(RATE_VERBS, t)
    if not m:
        return None
    verb = m.group(1)
    kind = ("cut" if re.match(r"cut|lower|ease|reduce", verb) else
            "hike" if re.match(r"hike|raise|tighten|increase", verb) else "hold")
    size = None
    ms = re.search(r"(\d+(?:\.\d+)?)\s*(bp|bps|basis points?)", t)
    if ms:
        size = float(ms.group(1))
    at_least = bool(re.search(r"at least|or more|more than", t))
    month = None
    mm = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december|"
                   r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b\.?,?\s*(\d{4})?", t)
    if mm:
        month = (MONTHS[mm.group(1)[:3]], int(mm.group(2)) if mm.group(2) else None)
    return {"area": cb[0], "bank": cb[1], "kind": kind, "size_bp": size, "at_least": at_least, "month": month}


def bis_policy_rate(area: str, start: date, get=http_get) -> list[tuple[date, float]]:
    url = f"https://stats.bis.org/api/v1/data/WS_CBPOL/D.{area}?format=csv&startPeriod={start.isoformat()}"
    rows = list(csv.DictReader(get(url).decode("utf-8", "replace").splitlines()))
    pts = []
    for r in rows:
        d = parse_date(r.get("TIME_PERIOD"))
        try:
            v = float(r.get("OBS_VALUE"))
        except (TypeError, ValueError):
            continue
        if d:
            pts.append((d, v))
    return sorted(pts), url


def resolve_rate_question(f: dict, today: date, get=http_get) -> dict:
    """Mechanical central-bank resolution from BIS daily policy rates."""
    q = parse_rate_question(f"{f.get('question', '')} {f.get('resolution_source', '')}")
    rd = parse_date(f.get("resolution_date"))
    if not q or not rd:
        return {"status": "unresolved", "reason": "could not parse the central bank, the verb or the date"}
    y, mth = (q["month"][1] or rd.year, q["month"][0]) if q["month"] else (rd.year, rd.month)
    month_start = date(y, mth, 1)
    try:
        pts, url = bis_policy_rate(q["area"], month_start - timedelta(days=45), get)
    except Exception as e:  # noqa: BLE001
        return {"status": "unresolved", "reason": f"BIS policy-rate download failed: {str(e)[:200]}"}
    before = [p for p in pts if p[0] < month_start]
    after = [p for p in pts if p[0] >= rd]
    if not before:
        return {"status": "unresolved", "reason": f"no BIS observation before {month_start}"}
    if not after:
        last = pts[-1][0] if pts else None
        return {"status": "waiting", "reason": f"BIS data run to {last}, before the resolution date {rd}; waiting for the update",
                "url": url}
    r0, (d1, r1) = before[-1][1], after[0]
    change = round((r1 - r0) * 100, 1)
    if q["kind"] == "cut":
        ok = change < -1
    elif q["kind"] == "hike":
        ok = change > 1
    else:
        ok = abs(change) <= 1
    if ok and q["size_bp"] is not None:
        ok = abs(change) >= q["size_bp"] - 5 if q["at_least"] else abs(abs(change) - q["size_bp"]) <= 5
    summary = (f"{q['bank']} policy rate {r0:g}% before {month_start:%B %Y} -> {r1:g}% on {d1} "
               f"({change:+g}bp); question asks for a {q['kind']}"
               + (f" of {'at least ' if q['at_least'] else ''}{q['size_bp']:g}bp" if q["size_bp"] else "") + ".")
    return {"status": "resolved", "outcome": "yes" if ok else "no", "summary": summary,
            "sources": [{"organisation": "BIS central bank policy rates (WS_CBPOL)", "url": url}]}


def parse_level_question(text: str, registry: list[dict]) -> dict | None:
    """'USD/BRL closes above 5.70 on 25 Dec 2026' -> {instrument row, side, level}."""
    reg = match_instrument(text, registry)
    if not reg:
        return None
    t = text.lower().replace("−", "-")
    m = re.search(rf"({ABOVE_WORDS}|{BELOW_WORDS})\s+(?:than\s+)?(?:the\s+)?(-?\d+(?:[.,]\d+)?)\s*(bp|bps|%|percent)?", t)
    if not m:
        return None
    word = m.group(1)
    side = "above" if re.fullmatch(ABOVE_WORDS, word) else "below"
    level = float(m.group(2).replace(",", "."))
    return {"instrument": reg["instrument"], "unit": reg.get("unit", ""), "side": side, "level": level}


def resolve_level_question(f: dict, marks_rows: list[dict], registry: list[dict], today: date) -> dict:
    q = parse_level_question(f"{f.get('question', '')} {f.get('resolution_source', '')}", registry)
    rd = parse_date(f.get("resolution_date"))
    if not q or not rd:
        return {"status": "unresolved", "reason": "could not parse the instrument, the direction or the level"}
    cands = [m for m in marks_rows if m.get("instrument") == q["instrument"] and m.get("value")
             and parse_date(m["date"]) and parse_date(m["date"]) <= rd]
    if not cands:
        return {"status": "waiting", "reason": f"no mark of {q['instrument']} on or before {rd} yet"}
    m = max(cands, key=lambda r: r["date"])
    md = parse_date(m["date"])
    allowed = 35 if m.get("frequency") == "monthly" else 5
    if (rd - md).days > allowed:
        return {"status": "waiting", "reason": f"latest mark of {q['instrument']} is dated {md}, more than {allowed} days before {rd}"}
    v = float(m["value"])
    ok = v >= q["level"] if q["side"] == "above" else v <= q["level"]
    summary = (f"{q['instrument']} marked {v:g} {m.get('unit', '')} on {md} ({m.get('source')}, {m.get('frequency', 'daily')}); "
               f"question asks for {q['side']} {q['level']:g}.")
    return {"status": "resolved", "outcome": "yes" if ok else "no", "summary": summary,
            "sources": [{"organisation": m.get("source", ""), "url": m.get("source_url", "")}]}


def classify_forecast(f: dict, registry: list[dict]) -> str:
    text = f"{f.get('question', '')} {f.get('resolution_source', '')}"
    if parse_rate_question(text):
        return "rate"
    if parse_level_question(text, registry):
        return "level"
    return "event"


def _sources_text(sources: list[dict]) -> str:
    return "; ".join(f"{s.get('organisation', '')} {s.get('url', '')}".strip() for s in sources if s.get("url"))


def settle_forecast(f: dict, outcome: str, method: str, summary: str, sources: list[dict], today: date) -> None:
    f["status"] = "resolved"
    f["outcome"] = outcome
    f["resolved_date"] = today.isoformat()
    f["result"] = (f"{AUTO_PREFIX} {outcome} on {today.isoformat()} by {method}: {summary} "
                   f"Sources: {_sources_text(sources)}. A Resolve form with this id overrides this.")


def resolve_issue(ref: str, kind: str, row: dict, found: str, extra: str = "") -> dict:
    title = f"{CONFIG.get('resolve_issue_title_prefix', '[RESOLVE?]')} {ref}"
    desc = (f"**{row.get('question')}**\n\nResolution date {row.get('resolution_date')}, resolution source: "
            f"{row.get('resolution_source') or 'not stated'}." if kind == "forecast" else
            f"**{row.get('action')} {row.get('instrument')} ({row.get('country')})**, horizon {row.get('horizon')}, "
            f"stop: {row.get('stop')}")
    body = (f"The daily resolver could not settle **{ref}** automatically.\n\n{desc}\n\n**What was found:** {found}\n\n"
            + (extra + "\n\n" if extra else "")
            + f"It tries again tomorrow. To settle it now, submit a [Resolve form]({REPO_URL}/issues/new?template=resolve.yml) "
              f"with id `{ref}`; a Resolve form always overrides the resolver, and this issue closes once the entry is resolved.")
    return {"title": title, "body": body, "ref": ref}


def last_session_finding(fid: str, auto_log: list[dict]) -> str | None:
    rows = [r for r in auto_log if r.get("id") == fid and r.get("kind") == "event check"]
    return f"{rows[-1]['date']}: {rows[-1]['detail']}" if rows else None


def process_forecasts(rows: list[dict], marks_rows: list[dict], registry: list[dict], today: date, get=http_get,
                      auto_log: list[dict] | None = None) -> tuple[list[dict], list[dict], list[str]]:
    changed, issues, log = [], [], []
    wait_days = int(CONFIG.get("mechanical_wait_days", 10))
    grace = int(CONFIG.get("session_resolve_grace_days", 2))
    for f in rows:
        if (f.get("status") or "open").strip().lower() != "open":
            continue
        rd = parse_date(f.get("resolution_date"))
        if not rd or today < rd:
            continue
        kind = classify_forecast(f, registry)
        if kind == "rate":
            res = resolve_rate_question(f, today, get)
            method = "official data (BIS central bank policy rates)"
        elif kind == "level":
            res = resolve_level_question(f, marks_rows, registry, today)
            method = "official data (registry marks)"
        else:
            method = "the forecast resolver session"
            if (today - rd).days < grace:
                log.append(f"{f['id']} event question: left for the forecast resolver session")
                continue
            seen = last_session_finding(f["id"], auto_log or [])
            res = {"status": "unresolved",
                   "reason": (f"not settled by the forecast resolver session {grace} or more days after the resolution "
                              f"date; its last finding: {seen}" if seen else
                              f"no forecast resolver session has settled it {grace} or more days after the resolution date")}
        if res.get("status") == "resolved":
            settle_forecast(f, res["outcome"], method, res.get("summary", ""), res.get("sources", []), today)
            changed.append(f)
            sc = score_forecast(f)
            log.append(f"{f['id']} resolved {res['outcome']} by {kind}: Brier me {sc['brier_me']}, market {sc['brier_market']}, "
                       f"Claude {sc['brier_claude']}")
            continue
        if res.get("status") == "waiting" and (today - rd).days < wait_days:
            log.append(f"{f['id']} waiting: {res.get('reason')}")
            continue
        found = res.get("reason") or res.get("summary") or "nothing conclusive"
        if res.get("summary") and res.get("reason"):
            found = f"{res['summary']} ({res['reason']})"
        srcs = res.get("all_sources") or res.get("sources") or []
        extra = ""
        if srcs:
            extra = "**Sources the search returned:**\n" + "\n".join(
                f"- {s.get('organisation', '')}: {s.get('url', '')}" + (f" — \"{s.get('quote')}\"" if s.get("quote") else "")
                for s in srcs)
        issues.append(resolve_issue(f["id"], "forecast", f, f"{kind} question; {found}", extra))
        log.append(f"{f['id']} not resolved ({kind}): {found}")
    return changed, issues, log


# ----------------------------------------------------------------------------- run
def append_auto_log(entries: list[dict], path: Path = AUTO_LOG) -> None:
    rows = read_rows(path)
    rows.extend(entries)
    write_rows(path, rows, AUTO_LOG_COLUMNS)


def run(today: date | None = None, root: Path = ROOT, dry_run: bool = False, get=http_get) -> dict:
    today = today or date.today()
    registry = load_registry(root / "data/ledger/instruments.csv")
    marks_rows = read_marks(root / "data/ledger/marks.csv")
    dec_path, fc_path = root / "data/ledger/decisions.csv", root / "data/ledger/forecasts.csv"
    decisions, forecasts = read_rows(dec_path), read_rows(fc_path)
    d_changed, d_issues, d_log = process_decisions(decisions, marks_rows, registry, today, root)
    f_changed, f_issues, f_log = process_forecasts(forecasts, marks_rows, registry, today, get=get,
                                                   auto_log=read_rows(root / "data/ledger/automation_log.csv"))
    entries = []
    for d in d_changed:
        sc = score_decision(d)
        entries.append({"date": today.isoformat(), "kind": "decision", "id": d["id"], "action": f"closed {d['outcome']}",
                        "detail": f"exit {d['exit_price']}; P&L {d['pnl_pct'] or 'n/a'}; Brier {sc['brier']}"})
    for f in f_changed:
        sc = score_forecast(f)
        entries.append({"date": today.isoformat(), "kind": "forecast", "id": f["id"], "action": f"resolved {f['outcome']}",
                        "detail": f"Brier me {sc['brier_me']}, market {sc['brier_market']}, Claude {sc['brier_claude']}"})
    for i in d_issues + f_issues:
        entries.append({"date": today.isoformat(), "kind": "issue", "id": i["ref"], "action": "[RESOLVE?]",
                        "detail": i["body"].split("**What was found:**")[-1].split("\n")[0].strip()[:200]})
    if not dry_run:
        if d_changed:
            write_rows(dec_path, decisions, DECISION_COLUMNS)
        if f_changed:
            write_rows(fc_path, forecasts, FORECAST_COLUMNS)
        if entries:
            append_auto_log(entries, root / "data/ledger/automation_log.csv")
    summary = (f"{len(d_changed)} decision(s) closed, {len(f_changed)} forecast(s) resolved, "
               f"{len(d_issues) + len(f_issues)} [RESOLVE?] issue(s)")
    return {"summary": summary, "closed": [d["id"] for d in d_changed], "resolved": [f["id"] for f in f_changed],
            "issues": d_issues + f_issues, "log": d_log + f_log}


# ----------------------------------------------------------------------------- the resolver session
def due_events(root: Path = ROOT, today: date | None = None) -> list[dict]:
    """Event forecasts past their resolution date, still open: what the session must try to settle. Blind: the
    question and how it resolves, never my, the market's or Claude's probability."""
    today = today or date.today()
    registry = load_registry(root / "data/ledger/instruments.csv")
    out = []
    for f in read_rows(root / "data/ledger/forecasts.csv"):
        rd = parse_date(f.get("resolution_date"))
        if (f.get("status") or "open").strip().lower() != "open" or not rd or today < rd:
            continue
        if classify_forecast(f, registry) != "event":
            continue
        out.append({"id": f["id"], "question": f.get("question"), "country": f.get("country"),
                    "resolution_date": f.get("resolution_date"), "resolution_source": f.get("resolution_source"),
                    "days_past": (today - rd).days})
    return out


def settle_events(payload: dict, root: Path = ROOT, today: date | None = None) -> dict:
    """Apply a session's findings atomically. Each result: {"id", "outcome": "yes"|"no"|"unresolved", "summary",
    "sources": [{"organisation", "url", "date", "quote"}]}. yes/no needs two independent sources (else the whole
    payload is rejected); "unresolved" is logged with its reason and the forecast stays open."""
    today = today or date.today()
    required = int(CONFIG.get("forecast_independent_sources_required", 2))
    model = str(payload.get("model") or "").strip()
    errors = [] if model else ["model is required (the session's model string)"]
    due = {e["id"]: e for e in due_events(root, today)}
    plan = []
    seen = set()
    for r in payload.get("results") or []:
        fid = str(r.get("id", "")).strip()
        if fid not in due:
            errors.append(f"{fid or '?'}: not an open event forecast past its resolution date")
            continue
        if fid in seen:
            errors.append(f"{fid}: listed twice")
            continue
        seen.add(fid)
        outcome = str(r.get("outcome", "")).strip().lower()
        summary = " ".join(str(r.get("summary") or "").split())
        if outcome not in ("yes", "no", "unresolved"):
            errors.append(f"{fid}: outcome must be yes, no or unresolved")
            continue
        if not summary:
            errors.append(f"{fid}: a summary is required (what settles it, with the date)")
            continue
        if outcome in ("yes", "no"):
            ok, kept = independent_sources(r.get("sources") or [], required)
            if not ok:
                errors.append(f"{fid}: only {len(kept)} independent source(s); {required} from different organisations "
                              "(different domains and names) are required to settle it")
                continue
            plan.append((fid, outcome, summary, kept))
        else:
            plan.append((fid, "unresolved", summary, []))
    if not (payload.get("results") or []):
        errors.append("no results")
    if errors:
        return {"ok": False, "errors": errors, "resolved": [], "unresolved": []}
    fc_path = root / "data/ledger/forecasts.csv"
    rows = read_rows(fc_path)
    by_id = {f["id"]: f for f in rows}
    entries, resolved, unresolved = [], [], []
    for fid, outcome, summary, kept in plan:
        if outcome == "unresolved":
            entries.append({"date": today.isoformat(), "kind": "event check", "id": fid, "action": "unresolved",
                            "detail": f"{summary} ({model})"[:300]})
            unresolved.append(fid)
            continue
        f = by_id[fid]
        settle_forecast(f, outcome, f"the forecast resolver session ({model}, web search)", summary, kept, today)
        sc = score_forecast(f)
        entries.append({"date": today.isoformat(), "kind": "forecast", "id": fid, "action": f"resolved {outcome}",
                        "detail": f"session ({model}); Brier me {sc['brier_me']}, market {sc['brier_market']}, Claude {sc['brier_claude']}"})
        resolved.append(fid)
    if resolved:
        write_rows(fc_path, rows, FORECAST_COLUMNS)
    append_auto_log(entries, root / "data/ledger/automation_log.csv")
    return {"ok": True, "errors": [], "resolved": resolved, "unresolved": unresolved}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", default="daily", choices=["daily", "events", "settle-events"])
    ap.add_argument("--file", default=None, help="settle-events: the session's findings (JSON, outside the repository)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--today", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    today = parse_date(a.today) if a.today else date.today()
    if a.cmd == "events":
        print(json.dumps(due_events(today=today), indent=1))
        return 0
    if a.cmd == "settle-events":
        try:
            payload = json.loads(Path(a.file).read_text(encoding="utf-8"))
        except (OSError, TypeError, json.JSONDecodeError) as e:
            print(f"REJECTED: cannot read the findings: {e}", file=sys.stderr)
            return 1
        res = settle_events(payload, today=today)
        print(json.dumps(res, indent=1))
        if not res["ok"]:
            print("REJECTED: nothing was written. Fix every error above and try again.", file=sys.stderr)
            return 1
        return 0
    res = run(today=today, dry_run=a.dry_run)
    for line in res["log"]:
        print(line)
    print(res["summary"])
    for i in res["issues"]:
        print(f"issue: {i['title']}")
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
