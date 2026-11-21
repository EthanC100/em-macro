"""The morning report: one phone screen, written after promote (results/night/morning/<Singapore date>.md).

Sections, in order: Promoted to main, Site and writers on main, Merged into dev, Failed or empty runs, Janus, v1.0 rules (D004), Lab sleeves,
Explorer findings, Pre-registrations awaiting me, Usage, Needs Ethan (at most 3, each with a recommendation).

v1.0 rules (D004) is read, never written: data/ledger/v1_rules.json on origin/main (ledger/v1_rules.py, written
after each official month-end v1.0 run). A triggered rule appears as a FLAG line, and also in Needs Ethan.

"Failed or empty runs" checks actual output, not the run's own status: a run logged as "merged" must have its
commits on origin/dev, and an explorer run must have rows in results/exploration/log.csv for the night. A chain stop
during the night whose reason is not a normal end of night (NORMAL_STOPS) is listed there too (Q011).

Janus is read, never written: the latest daily review and quick check from data/janus/records.jsonl through
ledger.janus (review_status, budget_status, open positions), against mandate C05. The records are main's: the
section fetches origin main itself (Q014; timeout, no prompt, git show, never a checkout) and prints "records as of
<newest recorded_at>". A failed fetch still reports, every line marked "[main not refreshed (fetch failed)]"; with no
origin/main copy the working tree's records are read and every line is marked "[dev copy]".

Site and writers on main (2026-11-17, after ledger-pages failed for six days with nobody told): the latest run on main
of ledger-pages (with the published site's own build time, read from its data/meta.json) and of ledger-daily, from
the public GitHub Actions API (read only, no token, as nightshift.guard), and the Janus checks (latest quick check,
due every 30 minutes, and the latest daily review) from the same records the Janus section reads. A failing or late
one is marked FAILING / STALE / LATE and also goes to Needs Ethan; an unreadable source is said, never skipped.

Usage (Q012) shows the run cap and safe mode of main's config/night.yaml, read through config.load_main (the guard's
loader) when the report is written and labelled "main's config at report time"; if it cannot be read the cap is
"unknown", never taken from the dev checkout.

An existing report for the date is never overwritten (Q013): the run exits 3, names the file and writes nothing,
unless its "Promoted to main" line differs from promoted(<date>) now (a 05:30 promote refused, the 06:30 rerun
passed), when the report is rewritten. --stdout prints and never writes.

python -m nightshift.morning [--date YYYY-MM-DD] [--dev origin/dev] [--needs "text => recommendation" ...] [--stdout]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import tempfile
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config as C
from . import guard as G
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


JANUS_REL = "data/janus/records.jsonl"
FETCH_TIMEOUT = 90                 # seconds; a hung fetch is a failed fetch, never a hung report
NOT_REFRESHED = "main not refreshed (fetch failed)"


def fetch_main(remote: str = "origin", branch: str = "main") -> str | None:
    """Refresh refs/remotes/<remote>/<branch> from the remote (Q014: in code, not only in the routine's prose).
    None when the fetch succeeded, else a short reason. Never raises and never prompts; touches only that ref."""
    try:
        r = subprocess.run(["git", "fetch", "--quiet", "--no-tags", remote,
                            f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}"],
                           cwd=ROOT, capture_output=True, text=True, timeout=FETCH_TIMEOUT,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"git fetch {remote} {branch}: {type(e).__name__}"
    return None if r.returncode == 0 else f"git fetch {remote} {branch}: exit {r.returncode}"


def janus_records() -> tuple[list[dict], str]:
    """The Janus records and the label their lines carry ("" when read from a freshly fetched origin/main).
    The Janus tasks write to main: fetch origin main, then read origin/main with git show (never a checkout). A
    failed fetch still reads the existing ref, labelled NOT_REFRESHED; with no origin/main copy at all the working
    tree's records are read, labelled "dev copy"."""
    from ledger import janus as J
    stale = fetch_main() is not None
    if _git("rev-parse", "--verify", "-q", "refs/remotes/origin/main^{commit}") \
            and _git("cat-file", "-t", f"origin/main:{JANUS_REL}") == "blob":
        live = _git("show", f"origin/main:{JANUS_REL}")
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            f.write(live + "\n")
        try:
            recs = J.load(Path(f.name))
        finally:
            os.unlink(f.name)
        return recs, NOT_REFRESHED if stale else ""
    return J.load(ROOT / JANUS_REL), "dev copy" + (f"; {NOT_REFRESHED}" if stale else "")


def _as_of(recs: list[dict]) -> str:
    """The newest recorded_at among the records, as YYYY-MM-DDTHH:MMZ (UTC)."""
    ts = []
    for r in recs:
        try:
            t = datetime.fromisoformat(str(r.get("recorded_at") or ""))
        except ValueError:
            continue
        ts.append((t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc))
    return f"{max(ts):%Y-%m-%dT%H:%M}Z" if ts else "no records"


def janus_section(today: date, records: tuple[list[dict], str] | None = None) -> list[str]:
    from ledger import janus as J
    recs, label = records if records is not None else janus_records()
    rs, bs = J.review_status(recs, today), J.budget_status(recs, today)
    pos = J.positions(recs)
    open_pos = [k for k, v in pos.items() if (v.get("status") or "") in ("open", "pending")]
    checks = [r for r in recs if r.get("type") == "check"]
    last_check = checks[-1] if checks else {}
    c05 = "complies" if (rs["status"] == "ok" and not bs["flags"]) else "does NOT comply"
    lines = [f"C05: {c05} (records as of {_as_of(recs)}). Last daily review {rs['last_date']} ({rs['status']}, "
             f"{rs['sources_read']} sources); {len(open_pos)} open/pending, {bs['risk_used_pct']:.2f}% at risk "
             "(budget 3-10%)" + (f"; reason: {bs['reason']}" if bs.get("reason") else "")]
    flags = rs["flags"] + bs["flags"]
    if flags:
        lines.append("Flags: " + "; ".join(flags))
    if last_check:
        lines.append(f"Last quick check {last_check.get('recorded_at', '')[:16]}Z: {_clip_words(last_check.get('result') or '')}")
    return [f"[{label}] {l}" for l in lines] if label else lines


# ----------------------------------------------------------------------------- site and writers on main
ACTIONS_API = f"https://api.github.com/repos/{G.REPO}/actions/workflows"
SITE_META = "https://ethanc100.github.io/em-macro/data/meta.json"
WATCHED_WORKFLOWS = (("ledger-pages", "ledger-pages.yml"), ("ledger-daily", "ledger-daily.yml"))
STALE_HOURS = 30            # both workflows succeed several times a day; a day and a bit with none is stale
QUICK_CHECK_LATE_HOURS = 2  # quick checks are due every 30 minutes (:15 and :45)
CONCLUSIVE = ("success", "failure", "timed_out", "startup_failure", "action_required")


def _ts(s: str | None) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _when(t: datetime | None) -> str:
    return f"{t.astimezone(timezone.utc):%d %b %H:%M}Z" if t else "?"


def _ago(t: datetime | None, now: datetime) -> str:
    if not t:
        return "?"
    h = (now - t).total_seconds() / 3600
    return f"{h:.0f} h ago" if h < 48 else f"{h / 24:.1f} days ago"


def workflow_line(name: str, wf: str, now: datetime, fetch=None) -> tuple[str, bool]:
    """'<name>: ok|FAILING|STALE ...' for the latest completed runs on main, and whether it needs attention."""
    d = (fetch or G._fetch)(f"{ACTIONS_API}/{wf}/runs?branch=main&per_page=50")
    if d is None:
        return f"{name}: status unknown (GitHub Actions API unreadable)", True
    runs = [r for r in d.get("workflow_runs") or [] if r.get("status") == "completed" and r.get("conclusion") in CONCLUSIVE]
    if not runs:
        return f"{name}: no completed run on main among the last 50", True
    last = runs[0]
    t = _ts(last.get("run_started_at") or last.get("created_at"))
    ok = next((r for r in runs if r.get("conclusion") == "success"), None)
    ok_t = _ts(ok.get("run_started_at") or ok.get("created_at")) if ok else None
    if last.get("conclusion") == "success":
        if t and (now - t).total_seconds() > STALE_HOURS * 3600:
            return f"{name}: STALE - no run on main since #{last.get('run_number')} {_when(t)} ({_ago(t, now)})", True
        return f"{name}: ok - #{last.get('run_number')} {_when(t)} succeeded", False
    streak = next((i for i, r in enumerate(runs) if r.get("conclusion") == "success"), len(runs))
    since = (f"last success #{ok.get('run_number')} {_when(ok_t)} ({_ago(ok_t, now)})" if ok
             else f"no success in the last {len(runs)} runs")
    return (f"{name}: FAILING - {streak}{'' if ok else '+'} run(s) in a row ({last.get('conclusion')}, latest #{last.get('run_number')} "
            f"{_when(t)}); {since}"), True


def site_built(now: datetime, fetch=None) -> tuple[str, bool]:
    """When the published site was built (its data/meta.json built_at), and whether that is stale. An unreadable
    site is said but not escalated on its own: the ledger-pages line already says whether deploys fail."""
    m = (fetch or G._fetch)(SITE_META)
    t = _ts((m or {}).get("built_at"))
    if not t:
        return "published site: build time unreadable", False
    stale = (now - t).total_seconds() > STALE_HOURS * 3600
    return f"published site built {_when(t)} ({_ago(t, now)}){' STALE' if stale else ''}", stale


def janus_checks_line(records: list[dict], label: str, today: date, now: datetime) -> tuple[str, bool]:
    """The latest quick check (a check record, or a quick-check run) and the latest daily review."""
    from ledger import janus as J
    qc = [_ts(r.get("recorded_at")) for r in records
          if r.get("type") == "check" or (r.get("type") == "run" and r.get("session") == "quick_check")]
    last = max((t for t in qc if t), default=None)
    late = not last or (now - last).total_seconds() > QUICK_CHECK_LATE_HOURS * 3600
    rs = J.review_status(records, today)
    line = (f"Janus checks: last quick check {_when(last)} ({_ago(last, now)}"
            + (", LATE: due every 30 min" if late else "") + f"); last daily review {rs['last_date'] or 'none'} "
            f"({rs['status'].upper() if rs['status'] != 'ok' else 'ok'})")
    return (f"[{label}] {line}" if label else line), late or rs["status"] != "ok"


def status_section(today: date, now: datetime, records: tuple[list[dict], str] | None, fetch=None) \
        -> tuple[list[str], list[str]]:
    """The section's lines, and the Needs Ethan lines for what is failing or late."""
    lines, needs = [], []
    for name, wf in WATCHED_WORKFLOWS:
        line, bad = workflow_line(name, wf, now, fetch)
        if name == "ledger-pages":
            site, stale = site_built(now, fetch)
            line, bad = f"{line}; {site}", bad or stale
        lines.append(line)
        if bad:
            needs.append(f"{line.split(':', 1)[0]} not healthy => open its latest failed run on main and fix the cause "
                         "(ledger-pages: the open ledger-pages-failure issue has the error)")
    if records is None:
        lines.append("Janus checks: records unreadable")
        needs.append("Janus records unreadable => check data/janus/records.jsonl on main")
    else:
        line, bad = janus_checks_line(records[0], records[1], today, now)
        lines.append(line)
        if bad:
            needs.append("Janus checks late or failing => check the Janus scheduled tasks ran and committed to main")
    return lines, needs


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


def usage_line(used: int) -> str:
    """The run count against main's cap and safe mode, read through C.load_main (the guard's loader) when the report
    is written (Q012). It is main's config at report time, not a cap recorded at each acquire. If main's config
    cannot be read the cap is unknown: never a fallback to the dev checkout's copy."""
    try:
        cfg = C.load_main()
        cap = C.run_cap(cfg)
        sm = bool((cfg.get("safe_mode") or {}).get("enabled"))
    except Exception:  # noqa: BLE001 - an unreadable main config is reported, never a crash or a dev fallback
        return f"{used} runs (cap unknown: main's config unreadable)"
    return f"{used} of {cap} runs (" + ("SAFE MODE, " if sm else "") + "main's config at report time)"


def build(day: date, dev: str, needs: list[str]) -> str:
    st = S.load()
    night = (day - timedelta(days=1)).isoformat()
    since = datetime.fromisoformat(f"{night}T22:00:00").replace(tzinfo=C.SGT)
    runs = night_runs(st, night)
    rows = exploration_rows()
    nd = {night, day.isoformat()}
    tonight = [r for r in rows if r.get("logged_on") in nd]
    drafts = sorted(p.name for p in (ROOT / "docs/prereg_drafts").glob("*.md") if p.name != "README.md")
    items = Q.parse((ROOT / "docs/queue.md").read_text(encoding="utf-8"))
    used = sum(1 for e in runs if e.get("routine") in S.COUNTED)
    try:
        jr = janus_records()
    except Exception:  # noqa: BLE001 - an unreadable record file is reported, never a crash
        jr = None
    status, status_needs = status_section(day, C.now_utc(), jr)
    L = [f"# Night shift, {night} -> {day.isoformat()}", "",
         f"**Promoted to main:** {promoted(day)}", "", "**Site and writers on main:**"]
    L += [f"- {x}" for x in status]
    L += ["", "**Merged into dev:**"]
    L += [f"- {m}" for m in merged_into_dev(dev, since)] or ["- nothing"]
    stop = chain_stop_line(st, night)
    bad = ([stop] if stop else []) + verify_runs(runs, dev, rows, nd)
    L += ["", "**Failed or empty runs:**"] + ([f"- {b}" for b in bad] or ["- none (outputs verified)"])
    L += ["", "**Janus:**"] + [f"- {x}" for x in janus_section(day, jr)]
    v1 = v1_rules_state()
    L += ["", "**v1.0 rules (D004):**"] + [f"- {x}" for x in v1_rules_section(v1)]
    L += ["", "**Lab sleeves:**"] + [f"- {x}" for x in lab_section(day)]
    nom = [r for r in tonight if r.get("nominated")]
    L += ["", f"**Explorer findings:** {len(tonight)} variant(s) logged, {len(nom)} nominated"
          + (": " + ", ".join(sorted({r['hypothesis_id'] for r in nom})) if nom else "")]
    L += ["", "**Pre-registrations awaiting me:** " + (", ".join(drafts) if drafts else "none")]
    L += ["", f"**Usage:** {usage_line(used)}"
          + f"; queue: {len(Q.approved(items))} approved, {sum(1 for i in items if i['status'] == 'blocked')} blocked"]
    v1_needs = [f"{f} => act on it at the next rebalance (docs/ledger/v1_rules.md); the monitor changes nothing"
                for f in ((v1 or {}).get("flags") or [])]
    auto = v1_needs + status_needs
    needs = auto + [n for n in needs if n not in auto]
    L += ["", "**Needs Ethan:**"] + ([f"- {n}" for n in needs[:3]] or ["- nothing"])
    if len(L) > MAX_LINES:
        L = L[:MAX_LINES - 1] + ["(truncated to one screen)"]
    return "\n".join(L) + "\n"


PROMOTED_LINE = re.compile(r"^\*\*Promoted to main:\*\* (.*)$", re.M)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=None, help="the morning's Singapore date (default today)")
    ap.add_argument("--dev", default="origin/dev")
    ap.add_argument("--needs", action="append", default=[], help='"issue => recommendation" (max 3 used)')
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args(argv)
    day = date.fromisoformat(a.date) if a.date else C.now_utc().astimezone(C.SGT).date()
    if a.stdout:
        print(build(day, a.dev, a.needs))
        return 0
    out = ROOT / f"results/night/morning/{day.isoformat()}.md"
    if out.exists():                       # Q013: checked before build(), so a refused run assembles nothing
        old = PROMOTED_LINE.search(out.read_text(encoding="utf-8"))
        now = promoted(day)
        if old is None or old.group(1).strip() == now:
            print(f"refused: {out.relative_to(ROOT)} already exists"
                  + ("" if old is None else " and its 'Promoted to main' line is unchanged")
                  + "; nothing written (use --stdout to print a report)", file=sys.stderr)
            return 3
        print(f"rewriting {out.relative_to(ROOT)}: Promoted to main changed from {old.group(1).strip()!r} to {now!r}",
              file=sys.stderr)
    text = build(day, a.dev, a.needs)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"written: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
