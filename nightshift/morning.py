"""The morning report: one phone screen, written after promote (results/night/morning/<Singapore date>.md).

Sections, in order: Promoted to main, Merged into dev, Failed or empty runs, Janus, v1.0 rules (D004), Lab sleeves,
Explorer findings, Pre-registrations awaiting me, Usage, Needs Ethan (at most 3, each with a recommendation).

v1.0 rules (D004) is read, never written: data/ledger/v1_rules.json on origin/main (ledger/v1_rules.py, written
after each official month-end v1.0 run). A triggered rule appears as a FLAG line, and also in Needs Ethan.

"Failed or empty runs" checks actual output, not the run's own status: a run logged as "merged" must have its
commits on origin/dev, and an explorer run must have rows in results/exploration/log.csv for the night. A chain stop
during the night whose reason is not a normal end of night (NORMAL_STOPS) is listed there too (Q011).

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


def _short(reason: str, n: int = 110) -> str:
    """One phone line per reason: long file lists become the first entries and a count."""
    if len(reason) <= n:
        return reason
    head, _, rest = reason.partition(": ")
    items = [x.strip(" '[]") for x in rest.split(",")]
    return f"{head}: {', '.join(items[:2])} (+{len(items) - 2} more)" if len(items) > 2 else reason[:n] + "..."


def promoted(day: date, main: str = "origin/main") -> str:
    """Whether the night's promotion reached main. The promote-merge workflow merges the PR (merge commit) only when
    every check passed and the tests went green; a promotion whose checked dev commit is not on main is flagged."""
    p = ROOT / f"results/night/promote/{day.isoformat()}.json"
    if not p.exists():
        return "no - promote did not run (no record)"
    r = json.loads(p.read_text(encoding="utf-8"))
    why = "; ".join(_short(x) for x in r.get("reasons") or []) or "checks passed"
    if r.get("mode") != "promote":
        return f"no - {'check only: ' if r.get('mode') == 'check only' else ''}{why}"
    pr = r.get("pr") if r.get("pr") not in (None, "", "none") else None
    if r.get("ok") and r.get("head") and on_branch(r["head"], main):
        return f"yes - merged into main ({pr or 'see the PR list'})"
    if r.get("ok"):
        return (f"NOT MERGED - {pr or 'no PR recorded'} is open: checks passed but promote-merge has not merged it "
                "(see its comment on the PR)")
    return f"NOT MERGED - {pr + ' left open; ' if pr else ''}{why}"


CHECK_RESULT_MAX = 240     # a quick-check result is one record: shown whole up to two phone lines


def _clip_words(text: str, n: int = CHECK_RESULT_MAX) -> str:
    """One line, never a partial word: whole up to n characters, else cut at the last word boundary + "..."."""
    text = " ".join(text.split())
    if len(text) <= n:
        return text
    head = text[:n - 2]                    # n - 3 characters plus one, to see whether a word ends at n - 3
    return (head.rsplit(" ", 1)[0] if " " in head else "") + "..."


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


# How a night normally ends (Q011): guard.next's stop reasons (after 05:00 / outside the window, run cap reached,
# nothing left to do; next --for night-worker: no approved items left) and night-start's "nothing to do". A chain stop
# with any other reason (e.g. dev conflicts with main) is listed under Failed or empty runs.
NORMAL_STOPS = ("after 05:00", "outside the night window", "run cap reached", "nothing left to do", "nothing to do",
                "no approved items left")


def normal_stop(reason: str) -> bool:
    return (reason or "").strip().lower().startswith(NORMAL_STOPS)


def chain_stop_line(st: dict, night: str) -> str | None:
    """'chain stopped HH:MM: <reason>' (Singapore time) when the chain was stopped during the reported night for a
    reason other than a normal end of night; else None. ``state stop`` adds nothing to the run log, so without this
    a stopped night reads as 'none (outputs verified)'."""
    cs = st.get("chain_stopped") or {}
    reason, at = (cs.get("reason") or "").strip(), cs.get("at")
    if not at or normal_stop(reason):
        return None
    try:
        ts = datetime.fromisoformat(at)
    except (TypeError, ValueError):
        return f"chain stopped (time unreadable: {at!r}): {_short(reason) or '(no reason given)'}"
    if C.night_of(ts).isoformat() != night:
        return None
    return f"chain stopped {ts.astimezone(C.SGT):%H:%M}: {_short(reason) or '(no reason given)'}"


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
        lines.append(f"Last quick check {last_check.get('recorded_at', '')[:16]}Z: {_clip_words(last_check.get('result') or '')}")
    return lines


def v1_rules_state() -> dict | None:
    """The latest D004 evaluation: origin/main's copy (the monitor writes to main), else the local file."""
    live = _git("show", "origin/main:data/ledger/v1_rules.json")
    if live:
        try:
            return json.loads(live)
        except ValueError:
            pass
    from ledger import v1_rules as V
    return V.load_state()


def v1_rules_section(state: dict | None) -> list[str]:
    from ledger import v1_rules as V
    return V.summary_lines(state)


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
    stop = chain_stop_line(st, night)
    bad = ([stop] if stop else []) + verify_runs(runs, dev, rows, nd)
    L += ["", "**Failed or empty runs:**"] + ([f"- {b}" for b in bad] or ["- none (outputs verified)"])
    L += ["", "**Janus:**"] + [f"- {x}" for x in janus_section(day)]
    v1 = v1_rules_state()
    L += ["", "**v1.0 rules (D004):**"] + [f"- {x}" for x in v1_rules_section(v1)]
    L += ["", "**Lab sleeves:**"] + [f"- {x}" for x in lab_section(day)]
    nom = [r for r in tonight if r.get("nominated")]
    L += ["", f"**Explorer findings:** {len(tonight)} variant(s) logged, {len(nom)} nominated"
          + (": " + ", ".join(sorted({r['hypothesis_id'] for r in nom})) if nom else "")]
    L += ["", "**Pre-registrations awaiting me:** " + (", ".join(drafts) if drafts else "none")]
    L += ["", f"**Usage:** {used} of {C.run_cap(cfg)} runs" + (" (SAFE MODE)" if sm else "")
          + f"; queue: {len(Q.approved(items))} approved, {sum(1 for i in items if i['status'] == 'blocked')} blocked"]
    v1_needs = [f"{f} => act on it at the next rebalance (docs/ledger/v1_rules.md); the monitor changes nothing"
                for f in ((v1 or {}).get("flags") or [])]
    needs = v1_needs + [n for n in needs if n not in v1_needs]
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
