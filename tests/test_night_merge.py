"""nightshift.merge: night-start's merge of main into dev. docs/queue.md rows merge by id (most advanced status wins),
docs/agent-state.json and results/opposition/calibration.csv stay dev's, and a conflict in any other file aborts.
Git checks run on temporary repositories; nothing here reads or writes the live queue or state."""
import json
import subprocess
from pathlib import Path

import pytest

from nightshift import merge as M
from nightshift import queue as Q

HEAD = """# Night-shift queue

Preamble.

<!-- queue:start -->
| id | type | status | title | acceptance test | branch/PR | opposition | ledger diff |
|---|---|---|---|---|---|---|---|
{rows}
<!-- queue:end -->
"""


def row(i, status="proposed", note="", opp=None):
    opp = ("no block, p=60%" if status in ("approved", "in-progress", "done") else "") if opp is None else opp
    return f"| {i} | bug | {status} | title {i} | test_{i.lower()} | {note} | {opp} | none |"


def queue(rows, sections=None):
    text = HEAD.format(rows="\n".join(rows))
    for qid, body in (sections or {}).items():
        text = text.rstrip("\n") + f"\n\n### {qid}\n\n{body}\n"
    return text


def by_id(text):
    return {r["id"]: r for r in Q.parse(text)}


# ------------------------------------------------------------------------------------------------ pure queue merge
@pytest.mark.parametrize("dev_s,main_s,want", [
    ("approved", "done", "done"), ("done", "approved", "done"), ("blocked", "in-progress", "blocked"),
    ("in-progress", "blocked", "blocked"), ("in-progress", "approved", "in-progress"),
    ("proposed", "approved", "approved"), ("done", "blocked", "done")])
def test_most_advanced_status_wins(dev_s, main_s, want):
    base = queue([row("Q001")])
    out = M.merge_queue(base, queue([row("Q001", dev_s)]), queue([row("Q001", main_s)]))
    assert by_id(out)["Q001"]["status"] == want


def test_one_sided_change_wins_over_rank():
    """Ethan, 11 Nov: rank decides only when both sides changed the row. A stale blocked row on main (equal to the
    base, e.g. after a refused promotion) never undoes an unblock or an in-progress item on dev."""
    base = queue([row("Q012", "blocked", "waiting"), row("Q013", "approved")])
    main = queue([row("Q012", "blocked", "waiting"), row("Q013", "approved")])
    for dev_s in ("approved", "in-progress", "proposed"):
        out = by_id(M.merge_queue(base, queue([row("Q012", dev_s, "unblocked"), row("Q013", "approved")]), main))
        assert out["Q012"]["status"] == dev_s
    # and the mirror: only main changed it (dev equal to base) -> main, even to a lower rank
    dev = queue([row("Q012", "blocked", "waiting"), row("Q013", "approved")])
    main2 = queue([row("Q012", "approved", "unblocked on main"), row("Q013", "approved")])
    assert by_id(M.merge_queue(base, dev, main2))["Q012"]["status"] == "approved"
    # both changed: rank decides
    out = by_id(M.merge_queue(base, queue([row("Q012", "approved", "x"), row("Q013", "approved")]),
                              queue([row("Q012", "done", "y"), row("Q013", "approved")])))
    assert out["Q012"]["status"] == "done"


def test_equal_status_one_sided_change_wins_else_dev():
    base = queue([row("Q001", "blocked", "awaiting Ethan"), row("Q002", "approved")])
    dev = queue([row("Q001", "blocked", "awaiting Ethan"), row("Q002", "approved", "dev note")])
    main = queue([row("Q001", "blocked", "closed by C06"), row("Q002", "approved", "main note")])
    out = by_id(M.merge_queue(base, dev, main))
    assert out["Q001"]["branch/PR"] == "closed by C06"      # only main changed it
    assert out["Q002"]["branch/PR"] == "dev note"           # both changed it: dev


def test_rows_keep_dev_order_and_main_only_rows_are_appended():
    base = queue([row("Q001"), row("Q002")])
    dev = queue([row("Q003"), row("Q002"), row("Q001")])
    main = queue([row("Q001"), row("Q002"), row("Q004")])
    assert [r["id"] for r in Q.parse(M.merge_queue(base, dev, main))] == ["Q003", "Q002", "Q001", "Q004"]


def test_sections_follow_the_three_way_rule_and_are_kept_in_id_order():
    base = queue([row("Q001", "blocked")], {"Q001": "Evidence 1."})
    dev = queue([row("Q002"), row("Q001", "blocked")], {"Q001": "Evidence 1.", "Q002": "Evidence 2 (dev)."})
    main = queue([row("Q001", "blocked", "closed")], {"Q001": "Evidence 1.\n**Closed** by C06."})
    out = M.merge_queue(base, dev, main)
    assert "**Closed** by C06." in out and "Evidence 2 (dev)." in out
    assert out.index("### Q001") < out.index("### Q002")
    assert Q.validate(Q.parse(out)) == []


def test_identical_inputs_round_trip_unchanged():
    t = queue([row("Q002", "approved"), row("Q001", "done")], {"Q001": "a", "Q002": "b"})
    assert M.merge_queue(t, t, t) == t


def test_reproduces_the_11_november_hand_resolution():
    """The conflict that stopped the chain on 10 Nov: main closed Q004 (same status, new note), dev had Q003 done
    and Q005-Q009. Ethan's resolution: main's Q004 row and closing note, dev's rows for everything else."""
    base = queue([row("Q003"), row("Q004", "blocked", "awaiting Ethan")], {"Q003": "e3", "Q004": "e4"})
    dev = queue([row("Q009", "approved"), row("Q008", "approved"), row("Q003", "done", "PR 27"),
                 row("Q004", "blocked", "awaiting Ethan"), row("Q005", "approved")],
                {"Q003": "e3", "Q004": "e4", "Q005": "e5", "Q008": "e8", "Q009": "e9"})
    main = queue([row("Q003"), row("Q004", "blocked", "closed by C06")],
                 {"Q003": "e3", "Q004": "e4\n**Closed (2026-11-10):** C06."})
    out = M.merge_queue(base, dev, main)
    rows = by_id(out)
    assert [r["id"] for r in Q.parse(out)] == ["Q009", "Q008", "Q003", "Q004", "Q005"]
    assert rows["Q003"]["status"] == "done" and rows["Q004"]["branch/PR"] == "closed by C06"
    assert "**Closed (2026-11-10):** C06." in out and "e9" in out


# ------------------------------------------------------------------------------------------------ git
def _git(repo, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=repo,
                          check=True, capture_output=True, text=True).stdout


def _write(repo, files):
    for p, t in files.items():
        f = repo / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(t, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c")


STATE = {"schema": 1, "night": "2026-11-10", "runs_used": 0, "log": []}
CAL = "date,target_id,p_works\n"


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "user.email", "t@t")
    _write(r, {"docs/queue.md": queue([row("Q001"), row("Q004", "blocked", "awaiting")], {"Q001": "e1", "Q004": "e4"}),
               "docs/agent-state.json": json.dumps(STATE, indent=1) + "\n",
               "results/opposition/calibration.csv": CAL, "docs/todo.md": "- [ ] one\n", "README.md": "x\n"})
    _git(r, "branch", "dev")
    return r


def _to_dev(repo, files):
    _git(repo, "checkout", "-q", "dev")
    _write(repo, files)


def _to_main(repo, files):
    _git(repo, "checkout", "-q", "main")
    _write(repo, files)


def test_git_conflicts_in_the_three_files_are_resolved(repo):
    _to_main(repo, {"docs/queue.md": queue([row("Q001"), row("Q004", "blocked", "closed by C06")],
                                           {"Q001": "e1", "Q004": "e4 closed"}),
                    "docs/agent-state.json": json.dumps({**STATE, "runs_used": 9}, indent=1) + "\n",
                    "results/opposition/calibration.csv": CAL + "2026-11-10,Q004,50\n", "README.md": "main\n"})
    dev_state = json.dumps({**STATE, "runs_used": 2, "log": [{"routine": "night-worker"}]}, indent=1) + "\n"
    _to_dev(repo, {"docs/queue.md": queue([row("Q002", "approved"), row("Q001", "done"),
                                           row("Q004", "blocked", "awaiting")], {"Q001": "e1", "Q002": "e2", "Q004": "e4"}),
                   "docs/agent-state.json": dev_state,
                   "results/opposition/calibration.csv": CAL + "2026-11-10,Q002,60\n"})
    res = M.main_into_dev(repo, "main")
    assert res["result"] == "merged" and res["exit"] == 0, res
    assert set(res["auto_resolved"]) == {"docs/queue.md", "docs/agent-state.json", "results/opposition/calibration.csv"}
    q = (repo / "docs/queue.md").read_text()
    rows = by_id(q)
    assert [r["id"] for r in Q.parse(q)] == ["Q002", "Q001", "Q004"]
    assert rows["Q001"]["status"] == "done" and rows["Q004"]["branch/PR"] == "closed by C06" and "e4 closed" in q
    assert (repo / "docs/agent-state.json").read_text() == dev_state
    assert (repo / "results/opposition/calibration.csv").read_text() == CAL + "2026-11-10,Q002,60\n"
    assert (repo / "README.md").read_text() == "main\n"                      # other files merge normally
    assert "<<<<<<<" not in q and _git(repo, "status", "--porcelain") == ""
    assert len(_git(repo, "log", "-1", "--format=%P").split()) == 2           # a real merge commit
    assert _git(repo, "log", "-1", "--format=%s").strip() == M.MESSAGE


def test_state_and_calibration_stay_devs_even_without_a_conflict(repo):
    _to_main(repo, {"docs/agent-state.json": json.dumps({**STATE, "note": "main edit"}, indent=1) + "\n",
                    "results/opposition/calibration.csv": "date,target_id,p_works\n2026-11-09,Q001,70\n"})
    _git(repo, "checkout", "-q", "dev")
    res = M.main_into_dev(repo, "main")
    assert res["result"] == "merged", res
    assert json.loads((repo / "docs/agent-state.json").read_text()) == STATE
    assert (repo / "results/opposition/calibration.csv").read_text() == CAL


def test_a_conflict_in_any_other_file_aborts_and_leaves_dev_untouched(repo):
    _to_main(repo, {"docs/todo.md": "- [x] one (main)\n",
                    "docs/queue.md": queue([row("Q001"), row("Q004", "blocked", "closed")], {"Q001": "e1", "Q004": "e4"})})
    _to_dev(repo, {"docs/todo.md": "- [x] one (dev)\n",
                   "docs/queue.md": queue([row("Q001", "approved"), row("Q004", "blocked", "x")], {"Q001": "e1", "Q004": "e4"})})
    before = _git(repo, "rev-parse", "HEAD")
    res = M.main_into_dev(repo, "main")
    assert res["result"] == "conflict" and res["exit"] == 3 and res["not_auto"] == ["docs/todo.md"]
    assert "docs/queue.md" in res["conflicts"]
    assert _git(repo, "rev-parse", "HEAD") == before and _git(repo, "status", "--porcelain") == ""
    assert subprocess.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=repo).returncode != 0


def test_a_merged_queue_that_does_not_validate_aborts(repo):
    # main marks Q001 done with no Opposition review: done outranks dev's row, and validate refuses it
    _to_main(repo, {"docs/queue.md": queue([row("Q001", "done", opp=""), row("Q004", "blocked", "awaiting")],
                                           {"Q001": "e1", "Q004": "e4"})})
    _to_dev(repo, {"docs/queue.md": queue([row("Q001", "approved"), row("Q004", "blocked", "awaiting")],
                                          {"Q001": "e1 dev", "Q004": "e4"})})
    before = _git(repo, "rev-parse", "HEAD")
    res = M.main_into_dev(repo, "main")
    assert res["result"] == "invalid-queue" and res["exit"] == 4 and any("Q001" in e for e in res["errors"])
    assert _git(repo, "rev-parse", "HEAD") == before and _git(repo, "status", "--porcelain") == ""


def test_up_to_date_and_cli_exit_codes(repo, capsys):
    _git(repo, "checkout", "-q", "dev")
    assert M.main(["main-into-dev", "--main", "main", "--repo", str(repo)]) == 0
    assert json.loads(capsys.readouterr().out)["result"] == "up-to-date"
    _to_main(repo, {"docs/todo.md": "main\n"})
    _to_dev(repo, {"docs/todo.md": "dev\n"})
    assert M.main(["main-into-dev", "--main", "main", "--repo", str(repo)]) == 3


def test_claude_md_keeps_main_sessions_off_the_night_files():
    t = (Path(__file__).resolve().parents[1] / "CLAUDE.md").read_text(encoding="utf-8")
    for f in M.AUTO:
        assert f in t, f
    assert "commit message or PR" in t
