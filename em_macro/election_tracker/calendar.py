"""Weekly calendar refresh: re-read each election's Wikipedia infobox date and cross-check
IFES ElectionGuide. Updates calendar.csv when a date is set or moves; logs every check.

Rules (see data/elections/calendar_NOTES.md):
* a plain date in the infobox ("6 June 2027", {{Start date|2028|5|8}}) sets `date` and
  upgrades `due_by` -> `scheduled`;
* a deadline ("By 11 November 2027", "No later than ...") updates `date` but never
  downgrades a `scheduled` row (some fixed-by-law dates are written as deadlines);
* month-only text ("By January 2028") changes nothing;
* a row whose date has passed becomes `held` (after the results window, vote + 3 days).
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

from . import wiki
from .common import CHECKS, load_calendar, load_config, save_calendar, today

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
DEADLINE_RE = re.compile(r"^\s*(by|no later than|on or before|not later than|before)\b", re.I)
EG_UPCOMING = "https://www.electionguide.org/elections/type/upcoming/"


def infobox_date(wikitext: str) -> tuple[str | None, dt.date | None, bool]:
    """(raw text, parsed date or None, is_deadline) from the infobox `election_date`."""
    m = re.search(r"\|\s*election_date\s*=\s*([^\n]*)", wikitext)
    if not m:
        return None, None, False
    raw = re.sub(r"<!--.*?-->|<ref[^>]*/>|<ref.*?</ref>", "", m.group(1), flags=re.S).strip()
    deadline = bool(DEADLINE_RE.search(raw))
    t = re.search(r"\{\{\s*start date[^|}]*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})\s*[|}]", raw, re.I)
    if t:
        return raw, dt.date(int(t[1]), int(t[2]), int(t[3])), deadline
    t = re.search(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})", raw, re.I)
    if t:
        return raw, dt.date(int(t[3]), MONTHS.index(t[2].lower()) + 1, int(t[1])), deadline
    t = re.search(r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2}),?\s+(\d{4})", raw, re.I)
    if t:
        return raw, dt.date(int(t[3]), MONTHS.index(t[1].lower()) + 1, int(t[2])), deadline
    return raw, None, deadline


def apply_infobox(row: pd.Series, parsed: dt.date | None, deadline: bool) -> tuple[pd.Series, str]:
    """Return the updated row and a description of the change ('' if none)."""
    if parsed is None or row["status"] not in ("scheduled", "due_by"):
        return row, ""
    new = row.copy()
    if not deadline:
        new["status"] = "scheduled"
    if parsed.isoformat() != row["date"]:
        new["date"] = parsed.isoformat()
    change = []
    if new["date"] != row["date"]:
        change.append(f"date {row['date']} -> {new['date']}")
    if new["status"] != row["status"]:
        change.append(f"status {row['status']} -> {new['status']}")
    return new, "; ".join(change)


def electionguide_upcoming() -> pd.DataFrame:
    r = requests.get(EG_UPCOMING, headers=wiki.UA, timeout=60)
    r.raise_for_status()
    rows = []
    for tr in BeautifulSoup(r.text, "lxml").select("table tr"):
        td = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        k = next((j for j, t in enumerate(td) if re.match(r"\d{4}-\d{2}-\d{2}", t)), None)
        if k is None or k < 2:               # cells: [flag], country, election, start date, ...
            continue
        a = tr.find("a", href=re.compile(r"/elections/id/"))
        rows.append({"country": td[k - 2], "election": td[k - 1], "date": td[k][:10],
                     "url": "https://www.electionguide.org" + a["href"].split("?")[0] if a else ""})
    return pd.DataFrame(rows, columns=["country", "election", "date", "url"])


def refresh() -> list[str]:
    cal, cfg = load_calendar(), load_config()
    now = today()
    try:
        eg = electionguide_upcoming()
    except Exception as e:                      # ElectionGuide is a cross-check only
        print(f"ElectionGuide unavailable: {e}")
        eg = pd.DataFrame(columns=["country", "election", "date", "url"])
    changes, log = [], []
    for i, row in cal.iterrows():
        c = cfg.get(row["id"], {})
        vote = dt.date.fromisoformat(row["date"])
        if row["status"] in ("scheduled", "due_by") and now > vote + dt.timedelta(days=3):
            cal.loc[i, "status"] = "held"
            changes.append(f"{row['id']}: status {row['status']} -> held")
            continue
        if row["status"] not in ("scheduled", "due_by") or not c.get("page"):
            continue
        rv = wiki.revision(c["page"])
        raw, parsed, deadline = infobox_date(rv["wikitext"]) if rv else (None, None, False)
        new, change = apply_infobox(row, parsed, deadline)
        if change:
            new["source_url"] = wiki.permalink(rv["title"], rv["revid"])
            cal.loc[i] = new
            changes.append(f"{row['id']}: {change} (Wikipedia: '{raw}')")
        egm = eg[eg["country"].str.contains(row["country"].split()[0], case=False, na=False)]
        egm = egm[(pd.to_datetime(egm["date"]) - pd.Timestamp(cal.loc[i, "date"])).abs() <= pd.Timedelta(days=3)]
        log.append({"check_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    "id": row["id"], "wikipedia_revid": rv["revid"] if rv else "",
                    "wikipedia_date_text": raw or "", "calendar_date": cal.loc[i, "date"],
                    "status": cal.loc[i, "status"], "electionguide": "; ".join(egm["url"]) or "not listed"})
    save_calendar(cal)
    if log:
        df = pd.DataFrame(log)
        df.to_csv(CHECKS, mode="a", index=False, header=not CHECKS.exists())
    for ch in changes:
        print("calendar:", ch)
    return changes
