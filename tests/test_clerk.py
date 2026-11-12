"""Ledger clerk (ledger/clerk.py): same parsing and checks as the intake workflow, writes through
scripts/ledger_commit.sh with the audit seal."""
import csv
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from conftest import frozen_copy, seed_ledger
from ledger import clerk, intake

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 6)

BLOCK = """DECISION RECORD
Date: 6 Nov 2026
Country: Mexico
Instrument: MX10Y
Action: Buy
Size: 1.5
Probability: 62
Horizon: 15 Jan 2027
Entry trigger: Buy at 9.20% yield
Stop / exit if wrong: Exit if the 10y yield rises above 9.80
Thesis: Banxico cuts faster than priced.
Key factors: Inflation; Fed.
What would change my mind: A hawkish turn.
How this differs from market consensus: Market prices two cuts; I expect four.
"""


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture()
def ledger_root(tmp_path):
    return seed_ledger(tmp_path / "repo")


def test_check_is_the_intake_result_and_writes_nothing(ledger_root, tmp_path):
    before = (ledger_root / "data/ledger/decisions.csv").read_text()
    res = clerk.check(BLOCK, TODAY, ledger_root)
    assert (ledger_root / "data/ledger/decisions.csv").read_text() == before
    same = intake.process_paste(BLOCK, "clerk", TODAY, ledger_root)
    assert res["ok"] and same["ok"] and res["id"] == same["id"]
    assert res["risk_comment"] == same["risk_comment"] and "Risk Manager: passed" in res["risk_comment"]
    assert "WOULD LOG: decision" in clerk.report(res, logged=False)


def test_check_lists_every_problem(ledger_root):
    res = clerk.check(BLOCK.replace("Size: 1.5", "Size: 2.5").replace("above 9.80", "badly"), TODAY, ledger_root)
    assert not res["ok"] and "Risk Manager: rejected" in res["risk_comment"]
    assert "at most 2%" in res["comment"] and "numeric" in res["comment"]
    assert "NOT LOGGED" in clerk.report(res, logged=False)
    # an event bet must be at half of quarter-Kelly: 62% -> 3%
    ev = BLOCK.replace("Size: 1.5", "Size: 1.0\nPosition type: event bet")
    res = clerk.check(ev, TODAY, ledger_root)
    assert not res["ok"] and "half of quarter-Kelly" in res["comment"]
    assert clerk.check(ev.replace("Size: 1.0", "Size: 3.0"), TODAY, ledger_root)["ok"]
    res = clerk.check(BLOCK.replace("Thesis: Banxico cuts faster than priced.\n", ""), TODAY, ledger_root)
    assert not res["ok"] and "`Thesis:`" in res["comment"]


def test_resolve_block(ledger_root):
    res = intake.process_paste("RESOLVE\nId: D001\nOutcome: wrong\nExit price or result: 120bp\nP&L: -0.5\n"
                               "Note: closed by hand\nafter the runoff poll\n", "clerk", TODAY, ledger_root)
    assert res["ok"] and res["kind"] == "resolve" and res["id"] == "D001"
    row = next(r for r in _rows(ledger_root / "data/ledger/decisions.csv") if r["id"] == "D001")
    assert (row["status"], row["outcome"], row["exit_price"], row["pnl_pct"]) == ("resolved", "wrong", "120bp", "-0.5")
    assert row["resolution_note"] == "closed by hand after the runoff poll"
    res = intake.process_paste("RESOLVE\nId: D001\nOutcome: maybe\n", "clerk", TODAY, ledger_root)
    assert not res["ok"] and "`Exit price or result:`" in res["comment"]


def test_resolve_never_changes_the_sealed_issue_field(ledger_root):
    """``issue`` is sealed with the entry (ledger/audit.py): a resolve of a decision or a forecast leaves it as logged."""
    before = {r["id"]: r["issue"] for r in _rows(ledger_root / "data/ledger/decisions.csv")}
    fbefore = {r["id"]: r["issue"] for r in _rows(ledger_root / "data/ledger/forecasts.csv")}
    assert intake.process_paste("RESOLVE\nId: D001\nOutcome: scratched\nExit price or result: duplicate\n",
                                "clerk", TODAY, ledger_root)["ok"]
    fid = sorted(fbefore)[0]
    assert intake.process_paste(f"RESOLVE\nId: {fid}\nOutcome: void\nExit price or result: race not called\n",
                                "77", TODAY, ledger_root)["ok"]
    assert {r["id"]: r["issue"] for r in _rows(ledger_root / "data/ledger/decisions.csv")} == before
    assert {r["id"]: r["issue"] for r in _rows(ledger_root / "data/ledger/forecasts.csv")} == fbefore


def test_stop_level_skips_account_percentages():
    from ledger.schema import stop_level
    assert stop_level("Max loss is the premium paid (2% of account). Exit early if March 2027 Brent futures "
                      "close below 85.00, or on a signed deal") == 85.0
    assert stop_level("Exit if the OAT-Bund spread tightens to 115bp") == 115.0
    assert stop_level("View is wrong if USD/BRL closes above 5.70") == 5.7
    assert stop_level("115bp") == 115.0 and stop_level("no level") is None


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def test_log_writes_through_ledger_commit_and_seals(tmp_path):
    """End to end on a throwaway repository with its own origin: check, ledger_commit.sh, seal, push."""
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    work.mkdir()
    for d in ("ledger", "scripts"):
        shutil.copytree(ROOT / d, work / d, ignore=shutil.ignore_patterns("__pycache__", "site"))
    seed_ledger(work)
    shutil.copytree(frozen_copy("data/janus"), work / "data/janus")
    (work / ".gitignore").write_text("__pycache__/\n")
    _git("init", "-q", "-b", "test", cwd=work)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A", cwd=work)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init", cwd=work)
    _git("init", "-q", "--bare", str(origin), cwd=tmp_path)
    _git("remote", "add", "origin", str(origin), cwd=work)
    _git("push", "-q", "origin", "test", cwd=work)
    _git("config", "user.name", "t", cwd=work)
    _git("config", "user.email", "t@t", cwd=work)
    block = tmp_path / "block.txt"
    block.write_text(BLOCK)
    p = subprocess.run([sys.executable, "-m", "ledger.clerk", "log", str(block), "--today", TODAY.isoformat(),
                        "--branch", "test"], cwd=work, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "Risk Manager: passed" in p.stdout and "LOGGED: decision D003" in p.stdout and "pushed" in p.stdout
    _git("fetch", "-q", "origin", cwd=work)
    assert "Ledger clerk: decision D003" in _git("log", "-1", "--format=%s", "origin/test", cwd=work)
    seals = _git("show", "origin/test:data/ledger/seals.jsonl", cwd=work).splitlines()
    new = [json.loads(x) for x in seals if '"D003"' in x]
    assert {(s["kind"], s["part"]) for s in new} == {("decision", "entry"), ("decision", "resolution")}   # status open
    assert _git("rev-parse", "--abbrev-ref", "HEAD", cwd=work).strip() == "test"     # checkout restored
    # a rejected block: nothing is pushed
    block.write_text(BLOCK.replace("Size: 1.5", "Size: 2.5"))
    p = subprocess.run([sys.executable, "-m", "ledger.clerk", "log", str(block), "--today", TODAY.isoformat(),
                        "--branch", "test"], cwd=work, capture_output=True, text=True)
    assert p.returncode == 1 and "NOT LOGGED" in p.stdout and "at most 2%" in p.stdout
    # resolving the sealed clerk entry through the clerk passes the audit seal (the resolve leaves ``issue`` alone)
    _git("merge", "-q", "--ff-only", "origin/test", cwd=work)          # the clerk checks against the local tree
    block.write_text("RESOLVE\nId: D003\nOutcome: scratched\nExit price or result: duplicate of D002\n"
                     "Note: Duplicate (same block, logged twice); no position.\n")
    p = subprocess.run([sys.executable, "-m", "ledger.clerk", "log", str(block), "--today", TODAY.isoformat(),
                        "--branch", "test"], cwd=work, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "LOGGED: resolve D003" in p.stdout and "pushed" in p.stdout
    _git("fetch", "-q", "origin", cwd=work)
    row = next(r for r in csv.DictReader(_git("show", "origin/test:data/ledger/decisions.csv", cwd=work).splitlines())
               if r["id"] == "D003")
    assert (row["status"], row["outcome"], row["issue"]) == ("resolved", "scratched", "clerk")
    seals = [json.loads(x) for x in _git("show", "origin/test:data/ledger/seals.jsonl", cwd=work).splitlines()
             if '"D003"' in x]
    assert sum(1 for s in seals if s["part"] == "resolution") == 2           # open, then resolved
