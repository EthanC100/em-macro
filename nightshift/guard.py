"""May a night run start now, and which routine runs next?

``python -m nightshift.guard check <routine>`` prints a JSON verdict and exits 0 (go) or 4 (do not run). Reasons:
outside the window, the night's cap reached, the chain was stopped, or an existing writer is busy:
* a workflow in ``busy_workflows`` queued or in progress (public GitHub Actions API, read only, no token);
* a fixed window in ``busy_windows_utc`` (the Janus daily review, the rebalance day).
If the Actions API cannot be read, the run does not start (fail safe) unless ``--allow-unknown`` is given.

``python -m nightshift.guard next`` prints the routine that should run next: ``night-worker`` while the approved
queue has items, alternating with ``night-explorer``; ``night-explorer`` when the approved queue is empty and
explorer hypotheses remain for the night; ``stop`` when nothing is left, the cap is reached or it is after 05:00.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime

from . import config as C
from . import queue as Q
from . import state as S

REPO = "EthanC100/em-macro"
API = f"https://api.github.com/repos/{REPO}/actions/runs"


def busy_runs(cfg: dict, fetch=None) -> list[str] | None:
    """Names of busy workflows queued or in progress, or None if the API could not be read."""
    fetch = fetch or _fetch
    names = set(cfg.get("busy_workflows") or [])
    out = []
    for status in ("in_progress", "queued"):
        d = fetch(f"{API}?status={status}&per_page=50")
        if d is None:
            return None
        out += [r["name"] for r in d.get("workflow_runs", []) if r.get("name") in names]
    return sorted(set(out))


def _fetch(url: str):
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": "em-macro-night-shift"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def in_busy_window(now: datetime, cfg: dict) -> str | None:
    t = now.astimezone(C.timezone.utc)
    for w in cfg.get("busy_windows_utc") or []:
        if w.get("day_of_month") and t.day != int(w["day_of_month"]):
            continue
        if C.hhmm(w["start"]) <= t.time() < C.hhmm(w["end"]):
            return w["name"]
    return None


def check(routine: str, now: datetime, cfg: dict, st: dict, busy: list[str] | None,
          allow_unknown: bool = False) -> dict:
    S.roll_night(st, now)
    cap = C.run_cap(cfg)
    reasons = []
    if routine in ("night-worker", "night-explorer", "night-start"):
        if not C.in_chain_window(now, cfg):
            reasons.append(f"outside the night window ({cfg['window']['start']}-{cfg['window']['chain_stop']} SGT)")
        if st.get("chain_stopped"):
            reasons.append(f"chain stopped: {st['chain_stopped'].get('reason')}")
    if routine in ("night-worker", "night-explorer") and int(st.get("runs_used") or 0) >= cap:
        reasons.append(f"run cap reached ({st['runs_used']} of {cap})")
    if routine == "promote" and not C.in_promote_window(now, cfg):
        reasons.append(f"outside the promote window ({cfg['window']['promote']}-{cfg['window']['promote_latest']} SGT)")
    w = in_busy_window(now, cfg)
    if w:
        reasons.append(f"inside the {w} window")
    if busy is None and not allow_unknown:
        reasons.append("could not read the GitHub Actions API: not starting (fail safe)")
    elif busy:
        reasons.append("busy: " + ", ".join(busy) + " running")
    return {"routine": routine, "go": not reasons, "reasons": reasons, "now_sgt": now.astimezone(C.SGT).isoformat(),
            "night": st.get("night"), "runs_used": st.get("runs_used"), "cap": cap}


def next_routine(now: datetime, cfg: dict, st: dict, items: list[dict], explorer_runs_tonight: int) -> dict:
    S.roll_night(st, now)
    cap = C.run_cap(cfg)
    if st.get("chain_stopped"):
        return {"next": "stop", "why": f"chain stopped: {st['chain_stopped'].get('reason')}"}
    if not C.in_chain_window(now, cfg):
        return {"next": "stop", "why": "after 05:00 SGT (or outside the window)"}
    if int(st.get("runs_used") or 0) >= cap:
        return {"next": "stop", "why": f"run cap reached ({st['runs_used']} of {cap})"}
    n_appr = len(Q.approved(items))
    explorer_left = explorer_runs_tonight < int((cfg.get("explorer") or {}).get("max_hypotheses_per_night", 3))
    if n_appr and (st.get("last_kind") != "worker" or not explorer_left):
        return {"next": "night-worker", "why": f"{n_appr} approved item(s)"}
    if explorer_left:
        return {"next": "night-explorer", "why": "alternating" if n_appr else "approved queue empty"}
    if n_appr:
        return {"next": "night-worker", "why": f"{n_appr} approved item(s); explorer done for the night"}
    return {"next": "stop", "why": "nothing left to do: approved queue empty and explorer done for the night"}


def explorer_runs(st: dict) -> int:
    return sum(1 for e in st.get("log", []) if e.get("routine") == "night-explorer"
               and e.get("finished_at") and C.night_of(datetime.fromisoformat(e["finished_at"])).isoformat()
               == st.get("night"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "next"])
    ap.add_argument("routine", nargs="?", default="night-worker")
    ap.add_argument("--allow-unknown", action="store_true")
    ap.add_argument("--now", default=None, help="ISO timestamp (testing and dry runs)")
    a = ap.parse_args(argv)
    now = datetime.fromisoformat(a.now) if a.now else C.now_utc()
    try:
        cfg = C.load_main()                     # main's config, fetched now: never dev's copy
    except C.MainConfigError as e:
        why = f"could not read main's config/night.yaml: not starting (fail safe): {e}"
        print(json.dumps({"routine": a.routine, "go": False, "reasons": [why]} if a.cmd == "check"
                         else {"next": "stop", "why": why}, indent=1))
        return 4
    st = S.load()
    if a.cmd == "check":
        v = check(a.routine, now, cfg, st, busy_runs(cfg), a.allow_unknown)
        print(json.dumps(v, indent=1))
        return 0 if v["go"] else 4
    items = Q.parse(Q.QUEUE.read_text(encoding="utf-8"))
    print(json.dumps(next_routine(now, cfg, st, items, explorer_runs(st)), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
