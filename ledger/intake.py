"""Issue intake: turn a filled-in GitHub issue form into a ledger entry.

Run by .github/workflows/ledger-intake.yml with the issue in environment variables
(ISSUE_NUMBER, ISSUE_TITLE, ISSUE_BODY, ISSUE_LABELS, ISSUE_USER, GITHUB_TOKEN). Writes a
result JSON (--out) with ok, kind, id, comment and the changed files. The workflow then
commits the files, comments with the id and closes the issue, or comments with the errors
and leaves it open. Everything here is also importable for tests: parse_issue_body(),
classify() and process().
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

from .schema import (AUTO_PREFIX, DECISION_COLUMNS, FORECAST_COLUMNS, REPORT_TYPES, kelly_size_pct, next_id,
                     parse_date, parse_number, parse_probability, position_type, validate_decision,
                     validate_forecast)
from .scoring import score_decision, score_forecast

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("decision", "forecast", "resolve", "report")
NO_RESPONSE = "_No response_"

# issue-form label -> CSV column
DECISION_FIELDS = {
    "Date": "date", "Country": "country", "Instrument": "instrument", "Action": "action",
    "Size (% of account at risk)": "size_pct", "Position type": "position_type",
    "Probability my view is right": "probability",
    "Horizon (date)": "horizon", "Entry trigger": "entry_trigger", "Stop / exit if wrong": "stop",
    "Thesis": "thesis", "Key factors": "key_factors", "What would change my mind": "change_mind",
    "How this differs from market consensus": "vs_consensus",
}
FORECAST_FIELDS = {
    "Question": "question", "My probability": "my_prob", "Market probability": "market_prob",
    "Market source": "market_source", "Claude probability (optional)": "claude_prob",
    "Resolution date": "resolution_date", "Resolution source": "resolution_source", "Country (optional)": "country",
}
RESOLVE_FIELDS = {"Decision or forecast id": "ref", "Outcome": "outcome", "Exit price or result": "result",
                  "P&L, % of account (optional)": "pnl", "Note (optional)": "note"}
REPORT_FIELDS = {"Title": "title", "Type": "type", "Country": "country", "Date (optional)": "date",
                 "Content": "content"}
OUTCOME_MAP = {"right": "right", "wrong": "wrong", "scratched": "scratched", "yes": "yes", "no": "no", "void": "void"}
ATTACHMENT_RE = re.compile(r"https://github\.com/user-attachments/(?:files|assets)/[^\s)>\"]+")
MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\((https://github\.com/user-attachments/[^\s)]+)\)")


def parse_issue_body(body: str) -> dict[str, str]:
    """Issue forms render as '### Label' headings followed by the value."""
    fields: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                fields[current] = "\n".join(buf).strip()
            current, buf = m.group(1).strip(), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        fields[current] = "\n".join(buf).strip()
    return {k: ("" if v.strip() == NO_RESPONSE else v) for k, v in fields.items()}


def classify(title: str, labels: list[str]) -> str | None:
    for k in KINDS:
        if f"ledger:{k}" in labels:
            return k
    m = re.match(r"\s*\[(decision|forecast|resolve|report)\]", title or "", re.I)
    return m.group(1).lower() if m else None


def _map(fields: dict, mapping: dict) -> dict:
    out = {}
    for label, col in mapping.items():
        # tolerate small label edits: match on the lower-cased label without the "(optional)" tag
        key = next((k for k in fields if k.lower().replace(" (optional)", "") == label.lower().replace(" (optional)", "")), None)
        out[col] = fields.get(key, "").strip() if key else ""
    return out


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_rows(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: (r.get(c) if r.get(c) is not None else "") for c in columns})


def _fmt_errors(errors: list[str]) -> str:
    return "\n".join(f"- {e}" for e in errors)


# ----------------------------------------------------------------------------- handlers
def handle_decision(fields: dict, issue: int, today: date, root: Path) -> dict:
    d = _map(fields, DECISION_FIELDS)
    rec = {c: "" for c in DECISION_COLUMNS}
    rec.update(d)
    rec["date"] = (parse_date(d["date"]) or today).isoformat() if parse_date(d["date"]) else d["date"]
    rec["position_type"] = position_type(rec) if rec.get("action") in ("Buy", "Sell") else ""
    from .risk import risk_check   # local import: risk reads the registry and the calendars
    rm = risk_check(rec, root, today)
    if not rm["ok"]:
        return {"ok": False, "kind": "decision", "risk_comment": rm["comment"],
                "comment": "This decision record was **not** logged (Risk Manager). Please edit the issue to fix:\n\n"
                           + _fmt_errors(rm["errors"]) + "\n\nThe workflow re-runs when the issue is edited."}
    path = root / "data/ledger/decisions.csv"
    rows = read_rows(path)
    rec["id"] = next_id([r.get("id", "") for r in rows], "D")
    rec["horizon"] = parse_date(d["horizon"]).isoformat()
    rec["size_pct"] = f"{parse_number(d['size_pct']):g}"
    rec["probability"] = f"{parse_probability(d['probability']):g}"
    rec["entry_level"] = _entry_level_from_trigger(d.get("entry_trigger", ""), rec)
    rec["status"] = "open"
    rec["issue"] = str(issue)
    rec["logged_at"] = today.isoformat()
    rows.append(rec)
    write_rows(path, rows, DECISION_COLUMNS)
    comment = (f"Logged as **{rec['id']}**: {rec['action']} {rec['instrument']} ({rec['country']}), "
               f"{rec['size_pct']}% at risk, p {rec['probability']}%, horizon {rec['horizon']}"
               f"{' (' + rec['position_type'] + ')' if rec['position_type'] else ''}.\n\n"
               + "\n".join(f"- {n}" for n in rm["notes"])
               + (f"\n- Entry level {rec['entry_level']} taken from the entry trigger (used for live P&L and the stop check)."
                  if rec["entry_level"] else
                  "\n- No numeric entry level found in the entry trigger: live P&L and the automatic horizon close need one "
                  "(add it to `entry_level` in data/ledger/decisions.csv, or state it in the trigger next time)."
                  if rec["action"] in ("Buy", "Sell") else "")
               + (f"\n- Risk Manager flags: {len(rm['flags'])} (see its comment)." if rm["flags"] else "")
               + "\n\nThe daily resolver closes it when the stop is hit or the horizon passes; resolve it earlier with the "
                 "*Resolve* form using this id. It appears in the app after the next build.")
    return {"ok": True, "kind": "decision", "id": rec["id"], "comment": comment, "risk_comment": rm["comment"],
            "files": ["data/ledger/decisions.csv"]}


def _entry_level_from_trigger(trigger: str, rec: dict) -> str:
    """A numeric entry level stated in the trigger ('at 5.40', 'entry 159bp', 'buy at 9.20% yield');
    blank when the trigger states none (a bare 'at market' entry is not a level)."""
    t = " ".join((trigger or "").split())
    m = re.search(r"(?:entry(?: level)?|at|@|from|level)\s*(?:of\s*)?[:=]?\s*(-?\d+(?:[.,]\d+)?)\s*(bp|bps|%|basis points?)?", t, re.I)
    if not m:
        return ""
    v = parse_number(m.group(1))
    return f"{v:g}" if v is not None else ""


def handle_forecast(fields: dict, issue: int, today: date, root: Path) -> dict:
    f = _map(fields, FORECAST_FIELDS)
    rec = {c: "" for c in FORECAST_COLUMNS}
    rec.update(f)
    rec["date"] = today.isoformat()
    errors, notes = validate_forecast(rec)
    if errors:
        return {"ok": False, "kind": "forecast",
                "comment": "This forecast was **not** logged. Please edit the issue to fix:\n\n"
                           + _fmt_errors(errors) + "\n\nThe workflow re-runs when the issue is edited."}
    path = root / "data/ledger/forecasts.csv"
    rows = read_rows(path)
    rec["id"] = next_id([r.get("id", "") for r in rows], "F")
    rec["question"] = " ".join(f["question"].split())
    rec["my_prob"] = f"{parse_probability(f['my_prob']):g}"
    rec["market_prob"] = f"{parse_probability(f['market_prob']):g}"
    rec["claude_prob"] = f"{parse_probability(f['claude_prob']):g}" if f["claude_prob"] else ""
    rec["resolution_date"] = parse_date(f["resolution_date"]).isoformat()
    rec["resolution_source"] = " ".join(f["resolution_source"].split())
    rec["status"] = "open"
    rec["issue"] = str(issue)
    rec["logged_at"] = today.isoformat()
    rows.append(rec)
    write_rows(path, rows, FORECAST_COLUMNS)
    comment = (f"Logged as **{rec['id']}**: \"{rec['question']}\" — me {rec['my_prob']}%, market {rec['market_prob']}%"
               + (f", Claude {rec['claude_prob']}%" if rec["claude_prob"] else "")
               + f"; resolves {rec['resolution_date']} by **{rec['resolution_source']}**.\n\n"
               "After the resolution date the daily resolver settles it from official data (prices, rates, "
               "central-bank decisions) or, for an event, from two independent sources found by web search; "
               "otherwise it opens a [RESOLVE?] issue. A *Resolve* form with this id always overrides it.")
    return {"ok": True, "kind": "forecast", "id": rec["id"], "comment": comment,
            "files": ["data/ledger/forecasts.csv"]}


def handle_resolve(fields: dict, issue: int, today: date, root: Path) -> dict:
    r = _map(fields, RESOLVE_FIELDS)
    ref = r["ref"].strip().upper()
    outcome = OUTCOME_MAP.get((r["outcome"].split("(")[0] or "").strip().lower(), "")
    errors = []
    if not re.match(r"^[DF]\d{3,}$", ref):
        errors.append(f"The id must look like D001 or F003; got {r['ref']!r}.")
    if not outcome:
        errors.append(f"Outcome {r['outcome']!r} is not recognised.")
    if not r["result"]:
        errors.append("Exit price or result is required.")
    if r["pnl"] and parse_number(r["pnl"]) is None:
        errors.append("P&L must be a number (% of account) if given.")
    if not errors:
        if ref.startswith("D"):
            path, columns, kind = root / "data/ledger/decisions.csv", DECISION_COLUMNS, "decision"
            if outcome not in ("right", "wrong", "scratched"):
                errors.append("A decision resolves right, wrong or scratched; choose one of those outcomes.")
        else:
            path, columns, kind = root / "data/ledger/forecasts.csv", FORECAST_COLUMNS, "forecast"
            if outcome not in ("yes", "no", "void"):
                errors.append("A forecast resolves yes, no or void; choose one of those outcomes.")
    if errors:
        return {"ok": False, "kind": "resolve", "comment": "Nothing was resolved. Please edit the issue to fix:\n\n"
                + _fmt_errors(errors) + "\n\nThe workflow re-runs when the issue is edited."}
    rows = read_rows(path)
    row = next((x for x in rows if x.get("id", "").upper() == ref), None)
    if row is None:
        return {"ok": False, "kind": "resolve", "comment": f"Nothing was resolved: no {kind} with id **{ref}** exists."}
    auto_field = "resolution_note" if kind == "decision" else "result"
    was_auto = (row.get(auto_field) or "").startswith(AUTO_PREFIX)
    if (row.get("status") or "open").lower() == "resolved" and not was_auto:
        return {"ok": False, "kind": "resolve", "comment": f"**{ref}** is already resolved ({row.get('outcome')}, {row.get('resolved_date')}). Edit the CSV by hand to change it."}
    override = (f" Overrides the automatic resolution of {row.get('resolved_date')} ({row.get('outcome')})."
                if was_auto else "")
    row["status"] = "resolved"
    row["outcome"] = outcome
    row["resolved_date"] = today.isoformat()
    if kind == "decision":
        row["exit_price"] = r["result"]
        row["pnl_pct"] = f"{parse_number(r['pnl']):g}" if r["pnl"] else ""
        note = " ".join(r["note"].split()) if r["note"] else ""
        row["resolution_note"] = (note + " " + override.strip()).strip() if override else note
        row["issue"] = f"{row.get('issue') or ''}{'; ' if row.get('issue') else ''}{issue}"
        sc = score_decision(row)
        lines = [f"Resolved **{ref}** as **{outcome}** on {today.isoformat()}." + (override if override else "")]
        if sc["brier"] is not None:
            lines.append(f"- Brier score: **{sc['brier']:.3f}** (p {row.get('probability')}%)"
                         + (f"; Claude {sc['brier_claude']:.3f}" if sc["brier_claude"] is not None else ""))
        if sc["pnl_pct"] is not None:
            lines.append(f"- P&L: **{sc['pnl_pct']:+.2f}%** of account")
        elif row.get("action") in ("Buy", "Sell"):
            lines.append("- P&L: not computable (needs a numeric entry level in the record, the stop and the exit price, or a P&L entered here).")
    else:
        row["result"] = " ".join(r["result"].split()) + (f" — {' '.join(r['note'].split())}" if r["note"] else "") + override
        row["issue"] = f"{row.get('issue') or ''}{'; ' if row.get('issue') else ''}{issue}"
        sc = score_forecast(row)
        lines = [f"Resolved **{ref}** as **{outcome}** on {today.isoformat()}." + (override if override else "")]
        if sc["brier_me"] is not None:
            lines.append(f"- Brier: me **{sc['brier_me']:.3f}**, market {sc['brier_market']:.3f}"
                         + (f", Claude {sc['brier_claude']:.3f}" if sc["brier_claude"] is not None else ""))
        else:
            lines.append("- Void: not scored.")
    write_rows(path, rows, columns)
    return {"ok": True, "kind": "resolve", "id": ref, "comment": "\n".join(lines),
            "files": [str(path.relative_to(root)).replace(os.sep, "/")]}


def _download(url: str, token: str | None, limit: int = 25_000_000) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": "ledger-intake"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read(limit + 1)
            return data if len(data) <= limit else None
    except Exception:  # noqa: BLE001 - any failure means "keep the link"
        return None


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:50] or "report"


def handle_report(fields: dict, issue: int, today: date, root: Path, token: str | None = None) -> dict:
    r = _map(fields, REPORT_FIELDS)
    errors = []
    if not r["title"]:
        errors.append("Title is required.")
    rtype = r["type"].strip().lower()
    if rtype not in REPORT_TYPES:
        errors.append(f"Type must be one of {', '.join(REPORT_TYPES)}.")
    if not r["country"]:
        errors.append("Country is required (use 'Global' if none).")
    d = parse_date(r["date"]) if r["date"] else today
    if r["date"] and d is None:
        errors.append(f"Date must be YYYY-MM-DD; got {r['date']!r}.")
    if not r["content"]:
        errors.append("Content is required: paste the text or attach a file.")
    if errors:
        return {"ok": False, "kind": "report", "comment": "This report was **not** archived. Please edit the issue to fix:\n\n"
                + _fmt_errors(errors) + "\n\nThe workflow re-runs when the issue is edited."}
    rep_dir = root / "data/ledger/reports"
    rep_dir.mkdir(parents=True, exist_ok=True)
    base = f"{d.isoformat()}_{slugify(r['title'])}"
    urls = MD_LINK_RE.findall(r["content"]) + ATTACHMENT_RE.findall(r["content"])
    urls = list(dict.fromkeys(urls))
    header = (f"---\ndate: {d.isoformat()}\ntitle: {r['title'].replace(chr(10), ' ')}\ntype: {rtype}\n"
              f"country: {r['country']}\nissue: {issue}\n---\n")
    files, notes = [], []
    body = r["content"]
    saved_pdf = False
    for u in urls:
        ext = Path(u.split("?")[0]).suffix.lower()
        data = _download(u, token)
        if data is None:
            notes.append(f"Attachment could not be downloaded and is kept as a link: {u}")
            continue
        if ext == ".pdf" or data[:5] == b"%PDF-":
            p = rep_dir / f"{base}.pdf"
            p.write_bytes(data)
            (rep_dir / f"{base}.meta.yml").write_text(header.strip("-\n") + "\n", encoding="utf-8")
            files += [str(p.relative_to(root)), str((rep_dir / f"{base}.meta.yml").relative_to(root))]
            saved_pdf = True
            notes.append("PDF attachment archived.")
        elif ext in (".md", ".txt", ".markdown"):
            text = data.decode("utf-8", errors="replace")
            _, text = _strip_front_matter(text)
            body = text + ("\n\n---\n\n" + body.replace(u, "").strip() if body.replace(u, "").strip() and not MD_LINK_RE.fullmatch(body.strip()) else "")
            notes.append("Text attachment archived as the report body.")
        else:
            notes.append(f"Attachment type {ext or 'unknown'} is kept as a link: {u}")
    if not saved_pdf or body.strip():
        md = rep_dir / f"{base}.md"
        if saved_pdf and not body.strip():
            pass
        else:
            md.write_text(header + "\n" + body.strip() + "\n", encoding="utf-8")
            files.append(str(md.relative_to(root)))
    files = [f.replace(os.sep, "/") for f in files]
    comment = (f"Archived **{r['title']}** ({rtype}, {r['country']}, {d.isoformat()}) as `{files[0]}`."
               + ("\n\n" + "\n".join(f"- {n}" for n in notes) if notes else "")
               + "\n\nIt appears under Reports after the next build.")
    return {"ok": True, "kind": "report", "id": base, "comment": comment, "files": files}


def _strip_front_matter(text: str) -> tuple[dict, str]:
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    return meta, text[m.end():]


def process(kind: str, body: str, issue: int, today: date, root: Path = ROOT, token: str | None = None) -> dict:
    fields = parse_issue_body(body)
    if kind == "decision":
        return handle_decision(fields, issue, today, root)
    if kind == "forecast":
        return handle_forecast(fields, issue, today, root)
    if kind == "resolve":
        return handle_resolve(fields, issue, today, root)
    if kind == "report":
        return handle_report(fields, issue, today, root, token)
    return {"ok": False, "kind": None, "comment": "This issue is not a ledger form; nothing to do."}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args(argv)
    labels = [s.strip() for s in os.environ.get("ISSUE_LABELS", "").split(",") if s.strip()]
    kind = classify(os.environ.get("ISSUE_TITLE", ""), labels)
    today = parse_date(os.environ.get("TODAY")) or date.today()
    issue = int(os.environ.get("ISSUE_NUMBER", "0") or 0)
    if kind is None:
        result = {"ok": False, "kind": None, "skip": True, "comment": ""}
    else:
        result = process(kind, os.environ.get("ISSUE_BODY", ""), issue, today, Path(a.root),
                         os.environ.get("GITHUB_TOKEN"))
    result.setdefault("files", [])
    Path(a.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "comment"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
