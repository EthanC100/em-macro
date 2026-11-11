"""night-start's merge of main into dev, with a deterministic resolution for the night shift's own three files.

Only these files are resolved automatically (whether git reports a conflict in them or not):

* ``docs/queue.md``: rows merged by id, three-way. A side that left the row as it was at the merge base yields to
  the side that changed it, whatever the status (so a stale ``blocked`` row on main cannot undo an unblock on dev).
  When both sides changed it, the most advanced status wins (done > blocked > in-progress > approved > proposed),
  and on equal status dev's row is kept. A row new on both sides is ranked the same way. Rows keep dev's order; rows only main has are appended in main's order.
  Evidence sections (``### Qnnn``) follow the same three-way rule (one-sided change wins, else the winning row's
  side), and are written in id order. The text around the table is dev's unless only main changed it.
* ``docs/agent-state.json`` and ``results/opposition/calibration.csv``: dev's version, always.

A conflict in any other file means ``git merge --abort`` and exit 3: night-start stops the chain and ends. A merged
queue that does not validate also aborts (exit 4). Nothing is pushed here; night-start pushes dev itself.

CLI: python -m nightshift.merge main-into-dev [--main origin/main] [--repo .] [--message M]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from . import queue as Q

QUEUE_PATH = "docs/queue.md"
DEV_WINS = ("docs/agent-state.json", "results/opposition/calibration.csv")
AUTO = (QUEUE_PATH, *DEV_WINS)
RANK = {"proposed": 0, "approved": 1, "in-progress": 2, "blocked": 3, "done": 4}
MESSAGE = "night-start: merge main into dev"
SECTION = re.compile(r"^### (Q\d{3,})[ \t]*$", re.M)


# ---------------------------------------------------------------------------------------------- queue.md, pure
def _split(text: str) -> tuple[str, str, dict[str, str]]:
    """(text before the table, text after the table up to the first evidence section, sections by id)."""
    pre, rest = text.split(Q.START, 1)
    _, post = rest.split(Q.END, 1)
    marks = list(SECTION.finditer(post))
    between = post[:marks[0].start()] if marks else post
    sections = {}
    for i, mk in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(post)
        sections[mk.group(1)] = post[mk.start():end].rstrip("\n") + "\n"
    return pre, between, sections


def _pick(base, dev, main, prefer_dev: bool = True):
    """Three-way pick of one value: a one-sided change wins; otherwise dev (or main if prefer_dev is False)."""
    if dev == main:
        return dev
    if dev == base:
        return main
    if main == base:
        return dev
    return dev if prefer_dev else main


def _rank(row: dict | None) -> int:
    return RANK.get((row or {}).get("status", ""), -1)


def merge_rows(base: list[dict], dev: list[dict], main: list[dict]) -> tuple[list[dict], dict[str, str]]:
    """Merge queue rows by id. Returns (rows in dev's order then main-only rows, {id: 'dev'|'main'} winners)."""
    b, d, m = ({r["id"]: r for r in rows} for rows in (base, dev, main))
    order = [r["id"] for r in dev] + [r["id"] for r in main if r["id"] not in d]
    out, won = [], {}
    for i in order:
        rd, rm, rb = d.get(i), m.get(i), b.get(i)
        if rm is None or rd == rm:
            side = "dev"
        elif rd is None:
            side = "main"
        elif rb is not None and rm == rb:       # only dev changed the row: dev wins, whatever the status
            side = "dev"
        elif rb is not None and rd == rb:       # only main changed it
            side = "main"
        else:                                   # both changed it (or new on both): rank, then dev
            side = "main" if _rank(rm) > _rank(rd) else "dev"
        won[i] = side
        out.append(dict(rd if side == "dev" else rm))
    return out, won


def merge_queue(base: str | None, dev: str, main: str) -> str:
    """Deterministic merge of three versions of docs/queue.md (base may be None when the file is new)."""
    pre_d, mid_d, sec_d = _split(dev)
    pre_m, mid_m, sec_m = _split(main)
    if base is not None and Q.START in base and Q.END in base:
        pre_b, mid_b, sec_b = _split(base)
        rows_b = Q.parse(base)
    else:
        pre_b = mid_b = None
        sec_b, rows_b = {}, []
    rows, won = merge_rows(rows_b, Q.parse(dev), Q.parse(main))
    pre, mid = _pick(pre_b, pre_d, pre_m), _pick(mid_b, mid_d, mid_m)
    ids = sorted(set(sec_d) | set(sec_m) | set(won), key=lambda q: int(q[1:]))
    secs = []
    for i in ids:
        sd, sm, sb = sec_d.get(i), sec_m.get(i), sec_b.get(i)
        if sd is None or sm is None:
            s = sd if sm is None else sm
        else:
            s = _pick(sb, sd, sm, prefer_dev=won.get(i, "dev") == "dev")
        if s is not None:
            secs.append(s)
    text = f"{pre}{Q.START}\n{Q.render_table(rows)}\n{Q.END}{mid}"
    if secs:
        text = text.rstrip("\n") + "\n\n" + "\n".join(secs)
    return text if text.endswith("\n") else text + "\n"


# ---------------------------------------------------------------------------------------------- git
def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=check)


def _show(repo: Path, rev: str, path: str) -> str | None:
    p = _git(repo, "show", f"{rev}:{path}", check=False)
    return p.stdout if p.returncode == 0 else None


def main_into_dev(repo: Path, main_ref: str = "origin/main", message: str = MESSAGE) -> dict:
    """Merge main_ref into the checked-out branch (dev). Returns a result dict; never pushes."""
    p = _git(repo, "merge", "--no-ff", "--no-commit", main_ref, check=False)
    if _git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode != 0:
        if p.returncode == 0:
            return {"result": "up-to-date", "exit": 0}
        return {"result": "error", "exit": 2, "detail": (p.stderr or p.stdout).strip()[-500:]}
    unmerged = sorted(f for f in _git(repo, "diff", "--name-only", "--diff-filter=U").stdout.split() if f)
    other = [f for f in unmerged if f not in AUTO]
    if other:
        _git(repo, "merge", "--abort")
        return {"result": "conflict", "exit": 3, "conflicts": unmerged, "not_auto": other}
    base = _git(repo, "merge-base", "HEAD", "MERGE_HEAD").stdout.strip()
    resolved = []
    for path in AUTO:
        dv, mn = _show(repo, "HEAD", path), _show(repo, "MERGE_HEAD", path)
        if dv is None:      # dev never had it: keep whatever git merged in
            continue
        if path == QUEUE_PATH and mn is not None and mn != dv:
            new = merge_queue(_show(repo, base, path), dv, mn)
            errs = Q.validate(Q.parse(new))
            if errs:
                _git(repo, "merge", "--abort")
                return {"result": "invalid-queue", "exit": 4, "errors": errs}
        else:
            new = dv
        f = repo / path
        if not f.exists() or f.read_text(encoding="utf-8") != new or path in unmerged:
            f.write_text(new, encoding="utf-8")
            resolved.append(path)
        _git(repo, "add", "--", path)
    _git(repo, "commit", "-q", "--no-edit", "-m", message)
    sha = _git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
    return {"result": "merged", "exit": 0, "commit": sha, "auto_resolved": [f for f in resolved if f in unmerged],
            "rewritten": resolved}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["main-into-dev"])
    ap.add_argument("--main", default="origin/main")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--message", default=MESSAGE)
    a = ap.parse_args(argv)
    res = main_into_dev(Path(a.repo).resolve(), a.main, a.message)
    print(json.dumps(res, indent=1))
    return int(res["exit"])


if __name__ == "__main__":
    sys.exit(main())
