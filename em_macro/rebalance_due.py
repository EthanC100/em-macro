"""Is this month's systematic rebalance still due? (queue item Q002, approved by Ethan 2026-11-12)

GitHub creates this repository's schedule events hours late and sometimes drops them, and the 3 Nov 2026 run
failed with no automatic retry. So a Claude Code scheduled task ("systematic-monthly kick") dispatches
systematic.yml at 07:23 UTC on the 3rd (input only_if_due=true), and two schedules stay as backups: the old
07:23 cron on the 3rd and a new one on the 4th. Only one of them may rebalance: the `due` job of systematic.yml runs
this gate first, and the update job runs only when it says so. The gate decides WHETHER the update job runs, never
what it computes (the update job's steps are unchanged).

    python -m em_macro.rebalance_due --event schedule --log rebalance_log.csv [--only-if-due false] [--today D]

Prints `run=true|false` and `reason=...` (lines for $GITHUB_OUTPUT). Standard library only, so the gate job needs
no install. The log is main's results/systematic/rebalance_log.csv, read after a fresh fetch: a scheduled run that
waited behind the kick's run was created before that run's commit, so its own checkout would not show it.

Rules:
  * a manual dispatch (only_if_due false) always runs: Ethan's re-runs after a D005 or v1.1 failure keep working;
  * otherwise (backup schedules, the kick) it runs only if this month's rebalance has not run: no row of the log
    has as_of the previous month (or later) and a run_date on or after the 1st of the current UTC month;
  * fail-open: if the log is missing or unreadable it runs (a missed rebalance is worse than a re-run, and a
    failure of the gate job itself also lets the update job run).
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from datetime import date, datetime, timezone
from pathlib import Path


def due_as_of(today: date) -> str:
    """The as_of month (YYYY-MM) of the rebalance due this month: the previous month (em_macro.rebalance)."""
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    return f"{y:04d}-{m:02d}"


def ran_this_month(log_text: str, today: date) -> dict | None:
    """The log row of this month's rebalance if it has run: as_of the previous month or later, run on or after the
    1st of this month. A re-run of last month's rebalance early this month (as_of two months back) does not count."""
    first, as_of = today.replace(day=1).isoformat(), due_as_of(today)
    rows = [r for r in csv.DictReader(io.StringIO(log_text))
            if (r.get("run_date") or "") >= first and (r.get("as_of") or "") >= as_of]
    if not rows:
        return None
    return max(rows, key=lambda r: r["run_date"])


def decide(event: str, only_if_due: bool, log_text: str | None, today: date) -> tuple[bool, str]:
    if event == "workflow_dispatch" and not only_if_due:
        return True, "manual dispatch: runs whatever the log says"
    if log_text is None:
        return True, "main's rebalance log could not be read: running (fail-open)"
    try:
        row = ran_this_month(log_text, today)
    except (csv.Error, KeyError, TypeError, ValueError) as e:
        return True, f"main's rebalance log could not be parsed ({type(e).__name__}): running (fail-open)"
    if row:
        return False, (f"already rebalanced this month: as_of {row.get('as_of')} ran {row['run_date']} "
                       f"({row.get('status')}); nothing to do")
    return True, f"due: the rebalance as of {due_as_of(today)} has not run since {today.replace(day=1).isoformat()}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", required=True)
    ap.add_argument("--only-if-due", default="false")
    ap.add_argument("--log", required=True, help="main's rebalance_log.csv (missing file = unreadable)")
    ap.add_argument("--today", default=None)
    a = ap.parse_args(argv)
    try:
        today = date.fromisoformat(a.today) if a.today else datetime.now(timezone.utc).date()
        p = Path(a.log)
        text = p.read_text(encoding="utf-8") if p.is_file() else None
        run, reason = decide(a.event, str(a.only_if_due).strip().lower() == "true", text, today)
    except Exception as e:                                           # never let the gate stop a rebalance
        run, reason = True, f"gate error ({type(e).__name__}): running (fail-open)"
    print(f"run={'true' if run else 'false'}")
    print("reason=" + reason.replace("\n", " "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
