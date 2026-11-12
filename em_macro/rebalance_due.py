"""Is this month's rebalance still to run?  Used by the `due` job of .github/workflows/systematic.yml.

    python3 -m em_macro.rebalance_due            # prints run=true|false (and writes it to $GITHUB_OUTPUT)

Only a dispatch started with the input ``only_if_due=true`` (the monthly kick) is ever skipped.  A
schedule event and a dispatch without the input always get run=true, exactly as before.  With the
input, run=false when results/systematic/rebalance_log.csv already has a row whose ``scheduled_date``
falls in the current UTC month (em_macro/rebalance.py writes one row per rebalance, scheduled for the
3rd of the month); otherwise run=true.  A missing or unreadable log means run=true: when in doubt the
rebalance runs.  Standard library only: the job needs no pip install.
"""
from __future__ import annotations

import csv
import os
from datetime import date, datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / "results" / "systematic" / "rebalance_log.csv"


def recorded(today: date, log: Path = LOG) -> bool:
    """True when the log has the rebalance scheduled in ``today``'s month."""
    try:
        with open(log, newline="", encoding="utf-8") as f:
            return any(str(r.get("scheduled_date", ""))[:7] == today.strftime("%Y-%m") for r in csv.DictReader(f))
    except (OSError, csv.Error, UnicodeDecodeError):
        return False


def decide(event: str, only_if_due: str, today: date, log: Path = LOG) -> tuple[bool, str]:
    """(run, reason).  Only workflow_dispatch with only_if_due == 'true' can be skipped."""
    if event != "workflow_dispatch" or str(only_if_due).strip().lower() != "true":
        return True, "no only_if_due request: run as usual"
    if recorded(today, log):
        return False, f"{today:%Y-%m} rebalance already recorded in rebalance_log.csv: nothing to do"
    return True, f"{today:%Y-%m} rebalance not recorded yet: run"


def main() -> None:
    today = datetime.now(timezone.utc).date()
    run, reason = decide(os.environ.get("EVENT_NAME", ""), os.environ.get("ONLY_IF_DUE", ""), today)
    print(f"due: run={str(run).lower()} ({reason})", flush=True)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"run={str(run).lower()}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"**systematic-monthly due check:** {reason}\n")


if __name__ == "__main__":
    main()
