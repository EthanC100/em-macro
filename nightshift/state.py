"""docs/agent-state.json: the night's lock, run counter and per-run log.

Every routine starts with no memory, so this file is the hand-over between runs:

* ``lock``: held by one night run at a time (night-worker, night-explorer, promote); stale after
  ``lock_stale_hours`` (2) and then taken over, with the take-over logged.
* ``night``, ``runs_used``: the counter of worker + explorer runs for the current night (reset when a new night
  starts), compared with the cap in config/night.yaml.
* ``last_kind``: "worker" or "explorer", so the chain alternates.
* ``log``: one entry per run (routine, start, end, outcome, queue items, commits, note). Kept to the last 300.

CLI (all write the file in place; ``scripts/night_commit.sh`` commits it to dev):
  python -m nightshift.state status
  python -m nightshift.state acquire <routine> [--session URL]   (exit 3 if held and not stale)
  python -m nightshift.state release <routine> --outcome merged|empty|failed|blocked|stopped|ok
                                     [--items Q001,Q002] [--commits sha,sha] [--note TEXT] [--kind worker|explorer]
  python -m nightshift.state stop --reason TEXT
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from . import config as C

STATE = C.ROOT / "docs/agent-state.json"
OUTCOMES = ("merged", "empty", "failed", "blocked", "stopped", "ok")
COUNTED = ("night-worker", "night-explorer")
LOG_KEEP = 300


def empty() -> dict:
    return {"schema": 1, "lock": None, "night": None, "runs_used": 0, "last_kind": None, "chain_stopped": None,
            "log": []}


def load(path: Path = STATE) -> dict:
    if not path.exists():
        return empty()
    s = json.loads(path.read_text(encoding="utf-8"))
    return {**empty(), **s}


def save(s: dict, path: Path = STATE) -> None:
    s["log"] = s["log"][-LOG_KEEP:]
    path.write_text(json.dumps(s, indent=1, sort_keys=False) + "\n", encoding="utf-8")


def _iso(ts: datetime) -> str:
    return ts.astimezone(C.SGT).replace(microsecond=0).isoformat()


def roll_night(s: dict, now: datetime) -> dict:
    """Start a new night's counter when the night has changed."""
    n = C.night_of(now).isoformat()
    if s.get("night") != n:
        s.update(night=n, runs_used=0, last_kind=None, chain_stopped=None)
    return s


def lock_is_stale(lock: dict | None, now: datetime, hours: float) -> bool:
    if not lock:
        return True
    at = datetime.fromisoformat(lock["acquired_at"])
    return now - at > timedelta(hours=hours)


def acquire(s: dict, routine: str, now: datetime, cfg: dict, session: str | None = None) -> tuple[bool, str]:
    roll_night(s, now)
    lk = s.get("lock")
    if lk and not lock_is_stale(lk, now, cfg.get("lock_stale_hours", 2)):
        return False, f"lock held by {lk['routine']} since {lk['acquired_at']}"
    note = ""
    if lk:
        note = f"took over a stale lock of {lk['routine']} from {lk['acquired_at']}"
        s["log"].append({"routine": lk["routine"], "started_at": lk["acquired_at"], "finished_at": _iso(now),
                         "outcome": "failed", "note": "lock went stale (run never released it)"})
    s["lock"] = {"routine": routine, "acquired_at": _iso(now), "session": session}
    return True, note or "acquired"


def release(s: dict, routine: str, now: datetime, outcome: str, items=(), commits=(), note: str = "",
            kind: str | None = None) -> dict:
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}")
    lk = s.get("lock") or {}
    entry = {"routine": routine, "started_at": lk.get("acquired_at"), "finished_at": _iso(now), "outcome": outcome,
             "items": list(items), "commits": list(commits), "note": note, "session": lk.get("session")}
    if routine in COUNTED:
        s["runs_used"] = int(s.get("runs_used") or 0) + 1
        entry["run"] = s["runs_used"]
        s["last_kind"] = kind or ("worker" if routine == "night-worker" else "explorer")
    s["log"].append(entry)
    if lk.get("routine") == routine:
        s["lock"] = None
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["status", "acquire", "release", "stop"])
    ap.add_argument("routine", nargs="?")
    ap.add_argument("--session", default=None)
    ap.add_argument("--outcome", default="ok")
    ap.add_argument("--items", default="")
    ap.add_argument("--commits", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--kind", default=None)
    ap.add_argument("--reason", default="")
    ap.add_argument("--state", default=str(STATE))
    a = ap.parse_args(argv)
    path, now = Path(a.state), C.now_utc()
    s = load(path)
    cfg = None
    if a.cmd in ("status", "acquire"):          # release and stop never need it, so they always record
        try:
            cfg = C.load_main()                 # main's config, fetched now: never dev's copy
        except C.MainConfigError as e:
            print(f"refused: could not read main's config/night.yaml (fail safe): {e}")
            return 3
    if a.cmd == "status":
        roll_night(s, now)
        print(json.dumps({k: s[k] for k in ("lock", "night", "runs_used", "last_kind", "chain_stopped")}
                         | {"cap": C.run_cap(cfg), "last_runs": s["log"][-5:]}, indent=1))
        return 0
    if a.cmd == "acquire":
        ok, msg = acquire(s, a.routine, now, cfg, a.session)
        print(msg)
        if not ok:
            return 3
        save(s, path)
        return 0
    if a.cmd == "release":
        split = lambda x: [v for v in x.split(",") if v]
        e = release(s, a.routine, now, a.outcome, split(a.items), split(a.commits), a.note, a.kind)
        save(s, path)
        print(json.dumps(e))
        return 0
    if a.cmd == "stop":
        roll_night(s, now)
        s["chain_stopped"] = {"reason": a.reason, "at": _iso(now)}
        save(s, path)
        print(f"chain stopped: {a.reason}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
