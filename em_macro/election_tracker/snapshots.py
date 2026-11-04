"""Point-in-time poll snapshots and poll averages.

Every snapshot stores, under data/elections/polls/<id>/:
    <retrieved date>_<tag>_rev<revid>.html.gz   raw HTML of the exact Wikipedia revision
    <retrieved date>_<tag>_rev<revid>.csv       parsed polls (one row per poll)
and appends a row to data/elections/polls/index.csv with the retrieval time, the revision
id and timestamp, a SHA-256 of the raw HTML, and the poll average.

* weekly  : latest revision; the average is computed as if the vote were the next day,
            i.e. the "current" poll average.
* final   : the last revision saved before the vote day starts (local time), fetched at any
            time afterwards (revisions are immutable, so this is point-in-time by
            construction); the average uses the vote date. This is the number the surprise uses.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
from zoneinfo import ZoneInfo

import pandas as pd

from . import wiki
from .common import ACTIVE, POLLS, days_to, load_calendar, load_config, post_issue, today
from .pollpages import parse_tables
from .polls import final_poll_average

INDEX = POLLS / "index.csv"
WINDOW_DAYS = 90


def vote_cutoff_utc(vote_date: str, tz: str) -> str:
    """Start of the vote day in local time, as an ISO UTC timestamp."""
    local = dt.datetime.combine(dt.date.fromisoformat(vote_date), dt.time(0, 0), ZoneInfo(tz))
    return local.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def config_gaps(c: dict) -> list[str]:
    return [k for k in ("poll_page", "options") if not c.get(k)]


def snapshot(eid: str, c: dict, vote_date: str, tag: str = "weekly") -> dict:
    retrieved = dt.datetime.now(dt.timezone.utc)
    before = vote_cutoff_utc(vote_date, c["tz"]) if tag == "final" else None
    rv = wiki.revision(c["poll_page"], before=before)
    if rv is None:
        raise RuntimeError(f"{eid}: poll page '{c['poll_page']}' not found")
    html = wiki.html(rv["title"], rv["revid"])
    folder = POLLS / eid
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{retrieved:%Y-%m-%d}_{tag}_rev{rv['revid']}"
    raw = html.encode()
    (folder / f"{stem}.html.gz").write_bytes(gzip.compress(raw, mtime=0))
    polls = parse_tables(html, c["options"], snapshot=rv["timestamp"][:10],
                         exclude_from_base=c.get("exclude_from_base"), table_filter=c.get("table_filter"),
                         exclude_pollsters=c.get("exclude_pollsters"))
    polls.to_csv(folder / f"{stem}.csv", index=False)
    ref = vote_date if tag == "final" else (dt.date.fromisoformat(rv["timestamp"][:10]) + dt.timedelta(days=1)).isoformat()
    avg = final_poll_average(polls, ref, list(c["options"]), c["race_kind"]) if len(polls) else {"n_pollsters": 0}
    row = {"id": eid, "tag": tag, "retrieved_utc": retrieved.isoformat(timespec="seconds"),
           "page": rv["title"], "revid": rv["revid"], "rev_timestamp": rv["timestamp"],
           "permalink": wiki.permalink(rv["title"], rv["revid"]), "sha256": hashlib.sha256(raw).hexdigest(),
           "raw_file": f"{eid}/{stem}.html.gz", "parsed_file": f"{eid}/{stem}.csv", "n_polls": len(polls),
           "ref_date": ref, "a": avg.get("a"), "b": avg.get("b"), "share_a": avg.get("share_a"),
           "share_b": avg.get("share_b"), "margin": avg.get("margin"), "window_days": avg.get("window_days"),
           "n_pollsters": avg.get("n_pollsters"), "pollsters": json.dumps(avg.get("pollsters", []))}
    pd.DataFrame([row]).to_csv(INDEX, mode="a", index=False, header=not INDEX.exists())
    print(f"{eid}: {tag} snapshot rev {rv['revid']} ({rv['timestamp']}), {len(polls)} polls, "
          f"average {avg.get('a')} {avg.get('share_a') or float('nan'):.1f} vs {avg.get('b')} "
          f"{avg.get('share_b') or float('nan'):.1f}, window {avg.get('window_days')}d, {avg.get('n_pollsters')} pollsters")
    return row


def latest(eid: str, tag: str | None = None) -> dict | None:
    if not INDEX.exists():
        return None
    ix = pd.read_csv(INDEX)
    ix = ix[(ix["id"] == eid) & ((ix["tag"] == tag) if tag else True)]
    return None if ix.empty else ix.iloc[-1].to_dict()


def weekly() -> list[dict]:
    """Snapshot every active election within 90 days of its vote date."""
    cal, cfg, out = load_calendar(), load_config(), []
    for _, row in cal.iterrows():
        n = days_to(row["date"])
        if row["status"] not in ACTIVE or not (0 <= n <= WINDOW_DAYS):
            continue
        c = cfg.get(row["id"], {})
        gaps = config_gaps(c)
        if gaps:
            post_issue(f"[ELECTION-CONFIG] {row['country']} {row['date']}: poll tracking not configured",
                       f"`{row['id']}` is {n} days away but `data/elections/tracker.yaml` has no {', '.join(gaps)}. "
                       "Add the Wikipedia opinion-polling page and the option columns so weekly snapshots can start.",
                       label="election-config", dedupe_prefix=f"[ELECTION-CONFIG] {row['country']} {row['date']}")
            continue
        out.append(snapshot(row["id"], c, row["date"], "weekly"))
    return out


def final(eid: str) -> dict:
    """Final pre-vote snapshot (idempotent)."""
    done = latest(eid, "final")
    if done:
        return done
    cal = load_calendar().set_index("id")
    if dt.date.fromisoformat(cal.loc[eid, "date"]) > today():
        raise RuntimeError(f"{eid}: the final snapshot can only be taken once the vote day has started")
    return snapshot(eid, load_config()[eid], cal.loc[eid, "date"], "final")
