"""Parse Wikipedia opinion-polling tables into one row per poll.

Generic: a table qualifies when it has a pollster column and a fieldwork-date column.
Option columns are matched by the per-election config (`options: {name: regex}`); the
fieldwork end date is the last day/month in the date cell, with the year taken from the
cell, else from the nearest preceding section heading, else inferred from the snapshot date.
"""
from __future__ import annotations

import io
import re

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
MONTH_RE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?", re.I)
POLLSTER_RE = re.compile(r"poll(ster|ing firm|ing organi[sz]ation)?|firm|agency|company|source", re.I)
DATE_RE = re.compile(r"date|fieldwork|conducted", re.I)
UNDECIDED_RE = re.compile(r"und|don.?t know|no ans|dk\b|unsure", re.I)
RESULT_ROW_RE = re.compile(r"\belection\b|\bresults?\b|\breferendum\b", re.I)
AGGREGATOR_RE = re.compile(r"aggregat|\baverage\b|poll of polls|ewybory", re.I)   # averages are not polls


def pollster_name(label: str) -> str:
    """Firm name without the commissioning client: 'IBRiS / Polsat News' -> 'IBRiS'."""
    return re.split(r"\s+/\s+|\s+for\s+|\s*\(for\s", label, maxsplit=1)[0].strip()


def fieldwork_end(cell: str, year_hint: int | None, snapshot: pd.Timestamp) -> pd.Timestamp | None:
    """Last date in a fieldwork cell such as '23–26 Oct', '28 Sep–2 Oct 2027', 'Oct 23–26'."""
    s = re.sub(r"\[[^\]]*\]", " ", str(cell))
    months = list(MONTH_RE.finditer(s))
    if not months:
        iso = re.findall(r"(\d{4})-(\d{2})-(\d{2})", s)
        return pd.Timestamp(*map(int, iso[-1])) if iso else None
    month = MONTHS[months[-1].group(1).lower()[:3]]
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", s)]
    days = [int(d) for d in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", re.sub(r"\b20\d{2}\b", " ", s)) if 1 <= int(d) <= 31]
    if not days:
        return None
    day = days[-1]
    if years:
        year = years[-1]
    elif year_hint:
        year = year_hint
    else:                                   # latest year that does not put the poll after the snapshot
        year = snapshot.year if pd.Timestamp(snapshot.year, month, 1) <= snapshot else snapshot.year - 1
    try:
        return pd.Timestamp(year, month, day)
    except ValueError:
        return None


def _num(x) -> float:
    s = re.sub(r"\[[^\]]*\]", "", str(x)).replace("%", "").replace(",", ".").strip()
    s = s.replace("–", "").replace("—", "").replace("−", "-")
    try:
        return float(s)
    except ValueError:
        return np.nan


def _flatten(cols) -> list[str]:
    out = []
    for c in cols:
        parts = [str(p) for p in (c if isinstance(c, tuple) else (c,))
                 if not str(p).startswith("Unnamed")]
        name = " ".join(dict.fromkeys(parts))               # drop duplicated header levels
        out.append(re.sub(r"\[[^\]]*\]", "", name).strip())
    return out


def parse_tables(html: str, options: dict[str, str], snapshot: str | pd.Timestamp,
                 exclude_from_base: list[str] | None = None, table_filter: str | None = None,
                 exclude_pollsters: str | None = None) -> pd.DataFrame:
    """All poll rows from all qualifying tables.

    options            {option name: regex matched against column headers}
    exclude_from_base  regexes for non-vote columns (undecided, none, ...) whose sum is
                       reported as `undecided` and removed from the base for "party" races;
                       default: undecided / don't know columns.
    table_filter       optional regex the preceding section heading must match.
    exclude_pollsters  optional regex of pollster labels to drop (e.g. party-commissioned polls);
                       aggregators and averages are always dropped.
    """
    snapshot = pd.Timestamp(snapshot)
    base_res = [re.compile(r, re.I) for r in (exclude_from_base if exclude_from_base is not None else [UNDECIDED_RE.pattern])]
    soup = BeautifulSoup(html, "lxml")
    heading, rows = "", []
    for el in soup.find_all(["h2", "h3", "h4", "table"]):
        if el.name != "table":
            heading = el.get_text(" ", strip=True)
            continue
        if "wikitable" not in (el.get("class") or []):
            continue
        if table_filter and not re.search(table_filter, heading, re.I):
            continue
        for sup in el.find_all("sup"):          # footnote markers
            sup.decompose()
        try:
            df = pd.read_html(io.StringIO(str(el)))[0]
        except ValueError:
            continue
        cols = _flatten(df.columns)
        df.columns = cols
        pc = next((c for c in cols if POLLSTER_RE.search(c)), None)
        dc = next((c for c in cols if DATE_RE.search(c)), None)
        if pc is None or dc is None or re.search(r"aggregat", pc, re.I):
            continue                            # aggregator summaries are not polls
        if not table_filter and re.search(r"seat", heading, re.I):
            continue                            # seat projections are not vote shares
        omap = {}
        for name, rx in options.items():
            hit = next((c for c in cols if re.fullmatch(rx, c, re.I) or re.search(rf"^(?:{rx})\b", c, re.I)), None)
            if hit:
                omap[name] = hit
        if len(omap) < 2:
            continue
        ucols = [c for c in cols if any(r.search(c) for r in base_res) and c not in omap.values()]
        ym = re.search(r"\b(20\d{2})\b", heading)
        year_hint = int(ym.group(1)) if ym else None
        for _, r in df.iterrows():
            label = re.sub(r"\[[^\]]*\]", "", str(r[pc])).strip()
            if not label or label.lower() in ("nan", pc.lower()) or label == str(r[dc]):
                continue                        # repeated header rows, event/annotation rows
            if RESULT_ROW_RE.search(label) or AGGREGATOR_RE.search(label):
                continue                        # previous results and poll averages shown in the table
            if exclude_pollsters and re.search(exclude_pollsters, label, re.I):
                continue
            pollster = pollster_name(label)
            end = fieldwork_end(r[dc], year_hint, snapshot)
            vals = {name: _num(r[col]) for name, col in omap.items()}
            if end is None or all(np.isnan(v) for v in vals.values()):
                continue
            und = [_num(r[c]) for c in ucols]
            rows.append({"pollster": pollster, "pollster_label": label, "fieldwork_end": end.date(), "fieldwork_cell": str(r[dc]),
                         **vals, "undecided": float(np.nansum(und)) if ucols else np.nan,
                         "section": heading})
    return pd.DataFrame(rows)
