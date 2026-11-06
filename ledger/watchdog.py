"""Marks watchdog: is data/ledger/marks.csv fresh?

    python -m ledger.watchdog --out /tmp/watchdog.json [--max-age-days 2] [--now 2026-11-06T12:00:00+00:00]

Reads the newest ``fetched_at`` in data/ledger/marks.csv (the time ledger-daily last fetched and
committed marks) and reports it as stale when it is more than ``--max-age-days`` (default 2) old.
The JSON it writes carries ``stale`` (bool), ``age_days``, ``last_fetch``, an issue ``title`` and
``body``; the workflows open "[ALERT] Ledger marks stale" when ``stale`` is true and close it when
it is false. Exit status is always 0 (the workflow decides what to do), unless ``--fail-if-stale``.

Added 2026-11-06: ledger-daily ran green on 4 and 5 Nov but committed nothing (``git add`` of a
log file that did not exist yet failed with its error hidden), so marks stopped at 4 Nov 10:10 UTC
with no alert. This check is independent of whether ledger-daily ran at all.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .marks import MARKS, read_marks

TITLE = "[ALERT] Ledger marks stale"


def check(now: datetime, max_age_days: float = 2.0, path: Path = MARKS) -> dict:
    rows = read_marks(path)
    fetched = [r.get("fetched_at") for r in rows if r.get("fetched_at") and r.get("value")]
    last = max(fetched) if fetched else None
    age = None
    if last:
        t = datetime.fromisoformat(last)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        age = round((now - t).total_seconds() / 86400, 2)
    stale = age is None or age > max_age_days
    obs = max((r.get("date") or "" for r in rows if r.get("value")), default="")
    body = (f"The newest mark in `data/ledger/marks.csv` was fetched at **{last or 'never'}**"
            f"{f' ({age:.1f} days ago)' if age is not None else ''}; the limit is {max_age_days:g} days. "
            f"Newest observation date: {obs or '-'}.\n\n"
            "ledger-daily should fetch and commit marks every morning (05:52 UTC, with a 09:22 UTC backup run). "
            "Check Actions > ledger-daily: a failed run opens its own alert; a green run that committed nothing "
            "points at the commit step. Re-run it with Actions > ledger-daily > Run workflow.\n\n"
            "Until marks are fresh, live P&L, stop checks and horizon closes use old prices. "
            "This issue closes itself when a fresh mark is committed.")
    return {"stale": stale, "age_days": age, "last_fetch": last, "last_observation": obs,
            "max_age_days": max_age_days, "title": TITLE, "body": body, "checked_at": now.isoformat()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-age-days", type=float, default=2.0)
    ap.add_argument("--now", default=None)
    ap.add_argument("--fail-if-stale", action="store_true")
    a = ap.parse_args(argv)
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    res = check(now, a.max_age_days)
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(("STALE: " if res["stale"] else "fresh: ") + f"last fetch {res['last_fetch']} ({res['age_days']} days)")
    return 1 if (a.fail_if_stale and res["stale"]) else 0


if __name__ == "__main__":
    sys.exit(main())
