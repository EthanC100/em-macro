"""Election tracker CLI (paper, observation only: every implied position is logged with size 0).

    python -m em_macro.election_tracker weekly            # calendar refresh + poll snapshots (<= 90 days)
    python -m em_macro.election_tracker daily             # pre-registrations due, results check, scoring
    python -m em_macro.election_tracker calendar          # calendar refresh only
    python -m em_macro.election_tracker polls             # poll snapshots only
    python -m em_macro.election_tracker prereg [--id ID --force]
    python -m em_macro.election_tracker final --id ID     # final pre-vote poll snapshot
    python -m em_macro.election_tracker results [--id ID --result "Morena=41.2,PAN=17.5" --source URL
                                                 --results-known YYYY-MM-DD --final]
    python -m em_macro.election_tracker score
    python -m em_macro.election_tracker show              # print the calendar
"""
from __future__ import annotations

import argparse

from . import alert, calendar, prereg, snapshots
from .common import load_calendar


def _shares(text: str) -> dict[str, float]:
    out = {}
    for part in text.split(","):
        k, v = part.rsplit("=", 1)
        out[k.strip()] = float(v)
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="election_tracker")
    ap.add_argument("cmd", choices=["weekly", "daily", "calendar", "polls", "prereg", "final", "results", "score", "show"])
    ap.add_argument("--id")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--result", help="manual result shares, e.g. 'Morena=41.2,PAN=17.5'")
    ap.add_argument("--source", default="manual entry")
    ap.add_argument("--results-known")
    ap.add_argument("--final", action="store_true", help="manual result is final, not provisional")
    a = ap.parse_args(argv)

    if a.cmd in ("weekly", "calendar"):
        calendar.refresh()
    if a.cmd in ("weekly", "polls"):
        snapshots.weekly()
    if a.cmd == "prereg":
        print(prereg.write(a.id, force=a.force) if a.id else prereg.due())
    if a.cmd == "final":
        snapshots.final(a.id)
    if a.cmd == "results" and a.id and a.result:
        alert.alert(a.id, _shares(a.result), a.source, a.results_known, provisional=not a.final)
    elif a.cmd == "results":
        alert.check()
    if a.cmd == "daily":
        prereg.due()
        alert.check()
        alert.score()
    if a.cmd == "score":
        alert.score()
    if a.cmd == "show":
        print(load_calendar().to_string(index=False))


if __name__ == "__main__":
    main()
