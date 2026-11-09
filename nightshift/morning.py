"""The morning report: one phone screen, written after promote (results/night/morning/<Singapore date>.md).

Sections, in order: Promoted to main, Merged into dev, Failed or empty runs, Janus, Lab sleeves, Explorer
findings, Pre-registrations awaiting me, Usage, Needs Ethan (at most 3, each with a recommendation).

"Failed or empty runs" checks actual output, not the run's own status: a run logged as "merged" must have its
commits on origin/dev, and an explorer run must have rows in results/exploration/log.csv for the night.

Janus is read, never written: the latest daily review and quick check from data/janus/records.jsonl through
ledger.janus (review_status, budget_status, open positions), against mandate C05.

python -m nightshift.morning [--date YYYY-MM-DD] [--dev origin/dev] [--needs "text => recommendation" ...]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import tempfile
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config as C
from . import queue as Q
from . import state as S

ROOT = C.ROOT
MAX_LINES = 40


def _git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def on_branch(commit: str, ref: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", commit, ref], cwd=ROOT,
                          capture_output=True).returncode == 0


def promoted(day: date) -> str:
    p = ROOT / f"results/night/promote/{day.isoformat()}.json"
    if not p.exists():
        return "no - promote did not run (no record)"
    r = json.loads(p.read_text(encoding="utf-8"))
    if r.get("ok") and r.get("mode") == "promote":
        return f"yes - PR opened with auto-merge ({r.get('pr', 'see PR list')})"
    why = "; ".join(r.get("reasons") or []) or "checks passed"
    return f"no - {'check only: ' if r.get('mode') == 'check only' else ''}{why}"


MERGE_SUBJECT = re.compile(r"^(Merge Q\d{3,}|Q\d{3,}:|night-start: merge main)")


def merged_into_dev(dev: str, since: datetime) -> list[str]:
    """Queue merges and the main sync on dev's first-parent line; bookkeeping commits are only counted."""
    out = [l for l in _git("log", dev, "--first-parent", f"--since={since.isoformat()}", "--format=%h %s").splitlines() if l]
    real = [l for l in out if MERGE_SUBJECT.match(l.split(" ", 1)[1] if " " in l else "")]
    other = len(out) - len(real)
    return real[:6] + ([f"({other} bookkeeping commit(s): state, queue, logs)"] if other else [])


def night_runs(st: dict, night: str) -> list[dict]:
    out = []
    for e in st.get("log", []):
        t = e.get("finished_at") or e.get("started_at")
        if t and C.night_of(datetime.fromisoformat(t)).isoformat() == night:
            out.append(e)
    return out


def verify_runs(runs: list[dict], dev: str, exploration_rows: list[dict], night_dates: set[str]) -> list[str]:
    bad = []
    for e in runs:
        tag = f"{e['routine']} {(e.get('finished_at') or '')[11:16]}"
        if e.get("outcome") in ("failed", "empty", "blocked"):
            bad.append(f"{tag}: {e['outcome']}" + (f" - {e['note']}" if e.get("note") else ""))
            continue
        if e.get("outcome") == "merged":
            missing = [c for c in e.get("commits", []) if not on_branch(c, dev)]
            if not e.get("commits") or missing:
                bad.append(f"{tag}: logged merged but commit(s) not on dev: {', '.join(missing) or 'none recorded'}")
        if e["routine"] == "night-explorer" and e.get("outcome") != "stopped":
            if not any(r.get("logged_on") in night_dates for r in exploration_rows):
                bad.append(f"{tag}: explorer run left no variant in results/exploration/log.csv")
    return bad


def janus_section(today: date) -> list[str]:
    from ledger import janus as J
    recs = J.load()
    live = _git("show", "origin/main:data/janus/records.jsonl")        # the existing Janus tasks write to main
    if live:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            f.write(live + "\n")
        recs = J.load(Path(f.name))
    rs, bs = J.review_status(recs, today), J.budget_status(recs, today)
    pos = J.positions(recs)
    open_pos = [k for k, v in pos.items() if (v.get("status") or "") in ("open", "pending")]
    checks = [r for r in recs if r.get("type") == "check"]
    last_check = checks[-1] if checks else {}
    c05 = "complies" if (rs["status"] == "ok" and not bs["flags"]) else "does NOT comply"
    lines = [f"C05: {c05}. Last daily review {rs['last_date']} ({rs['status']}, {rs['sources_read']} sources); "
             f"{len(open_pos)} open/pending, {bs['risk_used_pct']:.2f}% at risk (budget 3-10%)"
             + (f"; reason: {bs['reason']}" if bs.get("reason") else "")]
    flags = rs["flags"] + bs["flags"]
    if flags:
        lines.append("Flags: " + "; ".join(flags))
    if last_check:
        lines.append(f"Last quick check {last_check.get('recorded_at', '')[:16]}Z: {last_check.get('result', '')[:120]}")
    return lines


def lab_section(today: date) -> list[str]:
    from lab.book import build
    lb = build(today)
    if not lb["sleeves"]:
        return [f"none launched ({len(lb['proposed'])} proposed)" + (f"; errors: {len(lb['errors'])}" if lb["errors"] else "")]
    return [f"{s['id']} {s['instrument']} {s['direction']}: {s['status']}, {s['pnl_pct']:+.2f}%" for s in lb["sleeves"]][:4] \
        + [f"Lab at risk {lb['risk_used_pct']:.2f}% of 5%"]


def exploration_rows() -> list[dict]:
    p = ROOT / "results/exploration/log.csv"
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build(day: date, dev: str, needs: list[str]) -> str:
    cfg, st = C.load(), S.load()
    night = (day - timedelta(days=1)).isoformat()
    since = datetime.fromisoformat(f"{night}T22:00:00").replace(tzinfo=C.SGT)
    runs = night_runs(st, night)
    rows = exploration_rows()
    nd = {night, day.isoformat()}
    tonight = [r for r in rows if r.get("logged_on") in nd]
    drafts = sorted(p.name for p in (ROOT / "docs/prereg_drafts").glob("*.md") if p.name != "README.md")
    items = Q.parse((ROOT / "docs/queue.md").read_text(encoding="utf-8"))
    used = sum(1 for e in runs if e.get("routine") in S.COUNTED)
    sm = (cfg.get("safe_mode") or {}).get("enabled")
    L = [f"# Night shift, {night} -> {day.isoformat()}", "",
         f"**Promoted to main:** {promoted(day)}", "", "**Merged into dev:**"]
    L += [f"- {m}" for m in merged_into_dev(dev, since)] or ["- nothing"]
    bad = verify_runs(runs, dev, rows, nd)
    L += ["", "**Failed or empty runs:**"] + ([f"- {b}" for b in bad] or ["- none (outputs verified)"])
    L += ["", "**Janus:**"] + [f"- {x}" for x in janus_section(day)]
    L += ["", "**Lab sleeves:**"] + [f"- {x}" for x in lab_section(day)]
    nom = [r for r in tonight if r.get("nominated")]
    L += ["", f"**Explorer findings:** {len(tonight)} variant(s) logged, {len(nom)} nominated"
          + (": " + ", ".join(sorted({r['hypothesis_id'] for r in nom})) if nom else "")]
    L += ["", "**Pre-registrations awaiting me:** " + (", ".join(drafts) if drafts else "none")]
    L += ["", f"**Usage:** {used} of {C.run_cap(cfg)} runs" + (" (SAFE MODE)" if sm else "")
          + f"; queue: {len(Q.approved(items))} approved, {sum(1 for i in items if i['status'] == 'blocked')} blocked"]
    L += ["", "**Needs Ethan:**"] + ([f"- {n}" for n in needs[:3]] or ["- nothing"])
    if len(L) > MAX_LINES:
        L = L[:MAX_LINES - 1] + ["(truncated to one screen)"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=None, help="the morning's Singapore date (default today)")
    ap.add_argument("--dev", default="origin/dev")
    ap.add_argument("--needs", action="append", default=[], help='"issue => recommendation" (max 3 used)')
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args(argv)
    day = date.fromisoformat(a.date) if a.date else C.now_utc().astimezone(C.SGT).date()
    text = build(day, a.dev, a.needs)
    if a.stdout:
        print(text)
        return 0
    out = ROOT / f"results/night/morning/{day.isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"written: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
