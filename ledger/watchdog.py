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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .marks import MARKS, read_marks

TITLE = "[ALERT] Ledger marks stale"
# Q018 (approved by Ethan 2026-11-11): GitHub creates this repository's schedule events 5.5-10.5 hours late, so a
# Claude Code scheduled task ("ledger-daily kick", docs/agent-system.md) dispatches ledger-daily at 06:07 and 22:07
# UTC, with the crons kept as backups. A kick window counts as missed when no ledger-daily run (any event, not
# cancelled) started from 20 minutes before to 45 minutes after it.
# Not "[ALERT] ledger-daily ...": ledger-daily closes every open alert with that prefix when a run succeeds, which
# would close this one straight after a late run.
LATE_TITLE = "[ALERT] Kick window missed: ledger-daily late"
KICK_TIMES = ((6, 7), (22, 7))                       # UTC (hour, minute)
KICK_EARLY, KICK_LATE = timedelta(minutes=20), timedelta(minutes=45)   # 20: the kick skips while a run made
# up to 20 minutes earlier is still active, so such a run must count for the window (The Opposition, Q018)
KICK_FROM = datetime(2026, 11, 11, 22, 7, tzinfo=timezone.utc)   # the task's first scheduled firing


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
            "ledger-daily should fetch and commit marks twice a day: the ledger-daily kick task dispatches it at 06:07 and "
            "22:07 UTC, and its 05:52 and 09:22 UTC crons are late-running backups (Q018). "
            "Check Actions > ledger-daily: a failed run opens its own alert; a green run that committed nothing "
            "points at the commit step. Re-run it with Actions > ledger-daily > Run workflow.\n\n"
            "Until marks are fresh, live P&L, stop checks and horizon closes use old prices. "
            "This issue closes itself when a fresh mark is committed.")
    return {"stale": stale, "age_days": age, "last_fetch": last, "last_observation": obs,
            "max_age_days": max_age_days, "title": TITLE, "body": body, "checked_at": now.isoformat()}


def _utc(s) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def kick_windows(now: datetime, lookback_hours: float = 48) -> list[datetime]:
    """The kick times whose window has closed by ``now``, within the lookback and from the task's first firing."""
    out, day = [], (now - timedelta(hours=lookback_hours)).date()
    while day <= now.date():
        for h, m in KICK_TIMES:
            t = datetime(day.year, day.month, day.day, h, m, tzinfo=timezone.utc)
            if KICK_FROM <= t and t + KICK_LATE <= now and t >= now - timedelta(hours=lookback_hours):
                out.append(t)
        day += timedelta(days=1)
    return out


def late_check(runs, now: datetime, lookback_hours: float = 48) -> dict:
    """Q018: which closed kick windows had no ledger-daily run start inside them. ``runs`` is the Actions API's
    ``list workflow runs`` answer (``{"workflow_runs": [...]}``) or its list; a run's start is ``run_started_at``
    (else ``created_at``). The JSON matches the marks check, so .github/scripts/marks_alert.sh opens and closes
    "[ALERT] Kick window missed: ledger-daily late" from it."""
    runs = runs.get("workflow_runs", []) if isinstance(runs, dict) else list(runs or [])
    # a run cancelled before it did anything (replaced while pending in the concurrency group) does not count
    runs = [r for r in runs if r.get("conclusion") not in ("cancelled", "skipped")]
    starts = sorted(t for t in (_utc(r.get("run_started_at") or r.get("created_at")) for r in runs) if t)
    missed = [t for t in kick_windows(now, lookback_hours)
              if not any(t - KICK_EARLY <= s <= t + KICK_LATE for s in starts)]
    latest = starts[-1].isoformat() if starts else None
    body = ("ledger-daily did not start within its kick window (" + ", ".join(
        f"{t:%Y-%m-%d %H:%M} UTC" for t in missed) + "): no run (not cancelled) started from 20 minutes before to 45 minutes after. "
            f"Latest ledger-daily start: {latest or 'none'}.\n\n"
            "The \"ledger-daily kick\" Claude Code scheduled task (docs/agent-system.md) dispatches ledger-daily at 06:07 "
            "and 22:07 UTC because GitHub starts this repository's scheduled workflows hours late (Q018). Check the "
            "task's last run (claude.ai/code, Scheduled tasks) and its session, then start ledger-daily by hand: "
            "Actions > ledger-daily > Run workflow. The 23:07 UTC Janus review needs that evening's marks.\n\n"
            "This issue closes itself when every recent kick window has a run.") if missed else ""
    return {"stale": bool(missed), "late": bool(missed), "missed": [t.isoformat() for t in missed],
            "latest_start": latest, "title": LATE_TITLE, "body": body,
            "close_comment": f"ledger-daily started in every recent kick window (latest start {latest}).",
            "checked_at": now.isoformat()}


def lateness(event: str, started: datetime, schedule: str | None = None) -> str:
    """One line for the job summary: how long after its intended time this run started (Q018)."""
    if event == "schedule" and schedule:
        mi, hr = (int(x) for x in schedule.split()[:2])
        intended = started.replace(hour=hr, minute=mi, second=0, microsecond=0)
        if intended > started:
            intended -= timedelta(days=1)
        what = f"cron {schedule}"
    else:
        kicks = [started.replace(hour=h, minute=m, second=0, microsecond=0) - timedelta(days=d)
                 for d in (0, 1) for h, m in KICK_TIMES]
        intended = max(k for k in kicks if k <= started + timedelta(minutes=1))
        what = f"{event} (nearest kick {intended:%H:%M} UTC)"
    late = int((started - intended).total_seconds() // 60)
    return (f"Started {started:%Y-%m-%d %H:%M} UTC by {what}: {late} minutes after {intended:%H:%M} UTC"
            + (" (LATE: more than 45 minutes)" if late > 45 else ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-age-days", type=float, default=2.0)
    ap.add_argument("--now", default=None)
    ap.add_argument("--fail-if-stale", action="store_true")
    ap.add_argument("--late-runs", default=None,
                    help="Q018: a JSON file of ledger-daily's runs (Actions API); check the kick windows instead")
    ap.add_argument("--lateness", nargs=2, metavar=("EVENT", "STARTED_AT"), default=None,
                    help="Q018: print the job summary's lateness line for this run")
    ap.add_argument("--schedule", default=None, help="with --lateness: github.event.schedule")
    a = ap.parse_args(argv)
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    if a.lateness:
        print(lateness(a.lateness[0], _utc(a.lateness[1]) or now, a.schedule or None))
        return 0
    if a.late_runs:
        res = late_check(json.loads(Path(a.late_runs).read_text(encoding="utf-8")), now)
        if a.out:
            Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(("LATE: " + ", ".join(res["missed"])) if res["late"] else f"on time (latest start {res['latest_start']})")
        return 0
    res = check(now, a.max_age_days)
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(("STALE: " if res["stale"] else "fresh: ") + f"last fetch {res['last_fetch']} ({res['age_days']} days)")
    return 1 if (a.fail_if_stale and res["stale"]) else 0


if __name__ == "__main__":
    sys.exit(main())
