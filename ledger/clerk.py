"""Ledger clerk: log a pasted DECISION RECORD, FORECAST or RESOLVE block from a Claude Code session.

    python -m ledger.clerk check <file>     # the Risk Manager result and every problem; writes nothing
    python -m ledger.clerk log <file>       # check, then write through scripts/ledger_commit.sh (sealed, pushed)
    python -m ledger.clerk write <file>     # the write itself; run by scripts/ledger_commit.sh, not by hand

<file> holds the pasted block exactly as given (it may sit anywhere; ``-`` reads standard input). The parsing and
every check are the intake workflow's own (``ledger.intake.process_paste``): the same field parser as the
"Quick decision (paste)" issue form, the same required fields, the Risk Manager (``ledger.risk``) with its sizing
rules (2% cap for a continuous position; an event bet at half of quarter-Kelly on its probability), and the same
handlers that write data/ledger/decisions.csv or forecasts.csv. Nothing here re-implements a rule.

``log`` first runs the check on a scratch copy of the ledger. If anything is wrong it prints every problem and stops
(exit 1) with nothing written. Otherwise it hands the block to scripts/ledger_commit.sh, which, on a fresh checkout
of ``main``, re-runs the same handler (so the id is the next free one on main, not on a stale copy), seals the new
entry in the audit chain (``python -m ledger.audit seal``), verifies both chains, commits and pushes. The new id is
printed at the end. Runbook for sessions: docs/ledger/clerk.md.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from . import intake
from .schema import parse_date

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "clerk"          # the `issue` column of an entry logged by the clerk (no GitHub issue)
HEADERS = {"decision": "DECISION RECORD", "forecast": "FORECAST", "resolve": "RESOLVE"}


def read_block(path: str) -> str:
    return sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")


def scratch_root(root: Path = ROOT) -> Path:
    """A throwaway copy of the repository for the dry run: data/ledger is copied (the handlers write there);
    everything else the Risk Manager reads (registry, calendars, the algorithm's positions) is linked."""
    tmp = Path(tempfile.mkdtemp(prefix="ledger-clerk-"))
    for p in root.iterdir():
        if p.name in ("data", ".git"):
            continue
        (tmp / p.name).symlink_to(p, target_is_directory=p.is_dir())
    (tmp / "data").mkdir()
    for p in (root / "data").iterdir():
        if p.name == "ledger":
            shutil.copytree(p, tmp / "data/ledger")
        else:
            (tmp / "data" / p.name).symlink_to(p, target_is_directory=p.is_dir())
    return tmp


def run_block(body: str, today: date, root: Path) -> dict:
    """The intake workflow's own handling of a pasted block (writes into ``root``)."""
    res = intake.process_paste(body, SOURCE, today, root)
    res.setdefault("files", [])
    return res


def check(body: str, today: date, root: Path = ROOT) -> dict:
    tmp = scratch_root(root)
    try:
        return run_block(body, today, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def report(res: dict, logged: bool) -> str:
    out = []
    if res.get("risk_comment"):
        out += [res["risk_comment"].strip(), ""]
    out.append(res.get("comment", "").strip())
    out.append("")
    if res.get("ok"):
        out.append(f"{'LOGGED' if logged else 'WOULD LOG'}: {res.get('kind')} {res.get('id')}")
    else:
        out.append("NOT LOGGED: fix the problems above and run the clerk again.")
    return "\n".join(out)


def _git(*args: str, root: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout.strip()


def log(body: str, today: date, root: Path = ROOT, branch: str | None = None) -> tuple[int, str]:
    """Check, then write through scripts/ledger_commit.sh. Returns (exit code, report)."""
    res = check(body, today, root)
    if not res.get("ok"):
        return 1, report(res, logged=False)
    work = Path(tempfile.mkdtemp(prefix="ledger-clerk-"))         # outside the repository: the tree must stay clean
    block, out, msg = work / "block.txt", work / "result.json", work / "message.txt"
    block.write_text(body, encoding="utf-8")
    here = _git("rev-parse", "--abbrev-ref", "HEAD", root=root)
    env = {**os.environ, "LEDGER_MSG_FILE": str(msg)}
    if branch:
        env["LEDGER_BRANCH"] = branch
    cmd = ["bash", str(root / "scripts/ledger_commit.sh"), f"Ledger clerk: {res['kind']} (pasted {HEADERS[res['kind']]})",
           "--", sys.executable, "-m", "ledger.clerk", "write", str(block), "--today", today.isoformat(),
           "--out", str(out), "--message-file", str(msg)]
    p = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
    if here and here != "HEAD":
        subprocess.run(["git", "checkout", "-q", here], cwd=root)   # the script leaves a detached checkout
    final = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    text = report(final, logged=p.returncode == 0) if final else ""
    tail = (p.stdout + p.stderr).strip()
    if p.returncode != 0 or final is None or not final.get("ok"):
        return (p.returncode or 1), (text + "\n\n" if text else "") + f"scripts/ledger_commit.sh failed:\n{tail}"
    return 0, text + f"\n{tail}"


def write(body: str, today: date, out: Path | None, message_file: Path | None, root: Path = ROOT) -> int:
    """Run by scripts/ledger_commit.sh on the fresh checkout: write the entry (sealing follows in the script)."""
    res = run_block(body, today, root)
    if out:
        out.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    if message_file and res.get("ok"):
        what = res.get("id")
        message_file.write_text(f"Ledger clerk: {res['kind']} {what} (pasted {HEADERS[res['kind']]})\n", encoding="utf-8")
    print(report(res, logged=False) if not res.get("ok") else f"wrote {res['kind']} {res.get('id')}")
    return 0 if res.get("ok") else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("check", "log", "write"))
    ap.add_argument("file", help="the pasted block (- for standard input)")
    ap.add_argument("--today", default=None, help="logging date (YYYY-MM-DD); default today")
    ap.add_argument("--branch", default=None, help="push to this branch instead of main (testing only)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--message-file", default=None)
    a = ap.parse_args(argv)
    today = parse_date(a.today) if a.today else date.today()
    body = read_block(a.file)
    if a.command == "check":
        res = check(body, today)
        print(report(res, logged=False))
        return 0 if res.get("ok") else 1
    if a.command == "write":
        return write(body, today, Path(a.out) if a.out else None, Path(a.message_file) if a.message_file else None)
    code, text = log(body, today, branch=a.branch)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
