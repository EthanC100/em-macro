"""Record when each monthly rebalance was due and when it actually ran.

    python -m em_macro.rebalance      # after `systematic update`; the monthly workflow runs it

The workflow (.github/workflows/systematic.yml) is scheduled for the 3rd of every month, so
the rebalance that applies the positions "as of" month M is due on the 3rd of month M+1.
This stamps ``scheduled_date`` and ``run_date`` on results/systematic/positions.csv, keeps
one row per rebalance in results/systematic/rebalance_log.csv (a re-run of the same month
replaces its row) and says in the log when a run is late.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone

import pandas as pd

from .config import RESULTS

OUT = RESULTS / "systematic"
SCHEDULED_DAY = 3          # cron "23 7 3 * *" in the workflow
LOG_COLUMNS = ["as_of", "effective_from", "scheduled_date", "run_date", "days_late", "status", "n_positions"]


def scheduled_date(as_of: str) -> date:
    """Due date of the rebalance that applies the positions as of month ``as_of`` (YYYY-MM)."""
    return (pd.Period(as_of, "M") + 1).to_timestamp().date().replace(day=SCHEDULED_DAY)


def status_text(days_late: int) -> str:
    if days_late > 0:
        return f"LATE by {days_late} day{'s' if days_late != 1 else ''}"
    if days_late < 0:
        return f"early by {-days_late} day{'s' if days_late != -1 else ''}"
    return "on time"


def record(today: date | None = None, out=OUT) -> dict:
    today = today or datetime.now(timezone.utc).date()
    pos_file, log_file = out / "positions.csv", out / "rebalance_log.csv"
    pos = pd.read_csv(pos_file, dtype=str, keep_default_na=False)      # text in, text out: values untouched
    if pos.empty or "as_of" not in pos:
        sys.exit(f"{pos_file} has no positions to stamp")
    as_of, effective_from = pos["as_of"].iloc[0], pos["effective_from"].iloc[0]
    due = scheduled_date(as_of)
    days_late = (today - due).days
    row = {"as_of": as_of, "effective_from": effective_from, "scheduled_date": str(due), "run_date": str(today),
           "days_late": days_late, "status": status_text(days_late), "n_positions": len(pos)}
    pos["scheduled_date"], pos["run_date"] = str(due), str(today)
    pos.to_csv(pos_file, index=False)
    log = pd.read_csv(log_file, dtype=str) if log_file.exists() else pd.DataFrame(columns=LOG_COLUMNS)
    log = pd.concat([log[log["as_of"] != as_of], pd.DataFrame([row]).astype(str)], ignore_index=True)
    log = log.sort_values("as_of").reindex(columns=LOG_COLUMNS)
    log.to_csv(log_file, index=False)
    msg = (f"Rebalance as of {as_of} (positions effective {effective_from}): scheduled {due}, "
           f"ran {today}: {row['status']}.")
    print(msg, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(("### :warning: " if days_late > 0 else "### ") + msg + "\n")
    return row


if __name__ == "__main__":
    record()
