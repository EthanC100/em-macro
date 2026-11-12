"""The night shift (docs/agent-system.md): state, guard, queue, protected paths, promotion checks, logs, Lab book,
brief and the agent/routine files. No network, no real remote: git checks run on temporary repositories."""
import csv
import json
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from nightshift import brief as B
from nightshift import config as C
from nightshift import guard as G
from nightshift import logs as LG
from nightshift import promote as PR
from nightshift import protected as P
from nightshift import queue as Q
from nightshift import state as S
from conftest import frozen_copy

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures/night"
# Tests read fixture configs, never the live config/night.yaml or config/brief.yaml: those files hold operational
# switches (safe mode, caps, delivery) that Ethan flips without touching code, and flipping one must not turn main red.
CFG = C.load(FIXTURES / "night.yaml")
BRIEF_CFG = FIXTURES / "brief.yaml"


def sgt(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=C.SGT)


# ------------------------------------------------------------------------------------------------ config/state
def test_night_naming_and_windows():
    assert C.night_of(sgt("2026-11-09T23:00")) == date(2026, 11, 9)
    assert C.night_of(sgt("2026-11-10T04:59")) == date(2026, 11, 9)
    assert C.in_chain_window(sgt("2026-11-09T22:30"), CFG)
    assert C.in_chain_window(sgt("2026-11-10T04:59"), CFG)
    assert not C.in_chain_window(sgt("2026-11-10T05:00"), CFG)
    assert not C.in_chain_window(sgt("2026-11-09T22:29"), CFG)
    assert C.in_promote_window(sgt("2026-11-10T05:30"), CFG)
    assert not C.in_promote_window(sgt("2026-11-10T07:00"), CFG)


def _with_safe_mode(cfg: dict, **kw) -> dict:
    return {**cfg, "safe_mode": {**cfg["safe_mode"], **kw}}


def test_safe_mode_drops_cap_and_puts_explorer_on_sonnet():
    off = _with_safe_mode(CFG, enabled=False)
    on = _with_safe_mode(CFG, enabled=True)
    assert C.run_cap(off) == off["run_cap"] == 12 and C.explorer_model(off) == "opus"
    assert C.run_cap(on) == 4 and C.explorer_model(on) == "sonnet"
    assert C.run_cap(_with_safe_mode(CFG, enabled=True, run_cap=2)) == 2           # the safe-mode cap is read, not fixed
    assert C.run_cap({"run_cap": 9}) == 9 and C.explorer_model({}) == "opus"       # no safe_mode block = off


def test_safe_mode_cap_reaches_the_guard():
    st = S.empty()
    st["runs_used"], st["night"] = 4, "2026-11-09"
    t = sgt("2026-11-09T23:00")
    assert G.check("night-worker", t, _with_safe_mode(CFG, enabled=False), st, [])["go"]
    assert not G.check("night-worker", t, _with_safe_mode(CFG, enabled=True), st, [])["go"]


def test_live_configs_parse_and_cover_the_fixture_keys():
    """Shape only, no values: the live files may switch safe mode, caps or delivery freely, but they must still parse
    and carry every key the code reads (the fixtures list them)."""
    for live, fx in ((C.CONFIG, FIXTURES / "night.yaml"), (B.CFG, BRIEF_CFG)):
        a, b = yaml.safe_load(live.read_text(encoding="utf-8")), yaml.safe_load(fx.read_text(encoding="utf-8"))
        assert set(b) <= set(a), (live.name, set(b) - set(a))
    live = C.load()
    assert set(CFG["safe_mode"]) <= set(live["safe_mode"]) and set(CFG["window"]) <= set(live["window"])
    assert C.run_cap(live) > 0 and C.explorer_model(live) in {"opus", "sonnet"}


def test_lock_counter_and_stale_takeover():
    st, t0 = S.empty(), sgt("2026-11-09T22:31")
    ok, _ = S.acquire(st, "night-worker", t0, CFG)
    assert ok and st["night"] == "2026-11-09"
    ok, msg = S.acquire(st, "night-explorer", t0 + timedelta(minutes=30), CFG)
    assert not ok and "night-worker" in msg
    S.release(st, "night-worker", t0 + timedelta(minutes=40), "merged", ["Q001"], ["abc123"])
    assert st["runs_used"] == 1 and st["last_kind"] == "worker" and st["lock"] is None
    ok, _ = S.acquire(st, "night-explorer", t0 + timedelta(hours=1), CFG)
    ok2, msg2 = S.acquire(st, "night-worker", t0 + timedelta(hours=3, minutes=1), CFG)   # stale after 2 h
    assert ok and ok2 and "stale" in msg2 and st["log"][-1]["outcome"] == "failed"
    S.roll_night(st, sgt("2026-11-10T22:31"))
    assert st["runs_used"] == 0 and st["night"] == "2026-11-10"


def test_state_file_in_repo_is_valid(frozen_repo):
    st = S.load()
    assert set(S.empty()) <= set(st)


# ------------------------------------------------------------------------------------------------ guard
def test_guard_refuses_busy_writers_cap_window_and_unknown_api():
    st = S.empty()
    ok = G.check("night-worker", sgt("2026-11-09T23:00"), CFG, st, [])
    assert ok["go"], ok
    assert not G.check("night-worker", sgt("2026-11-09T23:00"), CFG, st, ["ledger-daily"])["go"]
    assert not G.check("night-worker", sgt("2026-11-09T23:00"), CFG, st, None)["go"]          # fail safe
    assert not G.check("night-worker", sgt("2026-11-10T05:10"), CFG, st, [])["go"]
    st["runs_used"], st["night"] = 12, "2026-11-09"
    assert not G.check("night-explorer", sgt("2026-11-09T23:00"), CFG, st, [])["go"]
    # the Janus daily review fires 23:07 UTC = 07:07 SGT, outside the chain window, but promote must not overlap it
    assert not G.check("promote", datetime(2026, 11, 9, 23, 10, tzinfo=timezone.utc), CFG, S.empty(), [])["go"]


def test_busy_runs_reads_only_named_workflows():
    def fake(url):
        if "in_progress" in url:
            return {"workflow_runs": [{"name": "ledger-daily"}, {"name": "something-else"}]}
        return {"workflow_runs": []}
    assert G.busy_runs(CFG, fetch=fake) == ["ledger-daily"]
    assert G.busy_runs(CFG, fetch=lambda u: None) is None


def _items(n_approved):
    return [{"id": f"Q00{i}", "type": "bug", "status": "approved" if i <= n_approved else "done",
             "title": "", "acceptance test": "x", "branch/PR": "", "opposition": "no block, p=50%",
             "ledger diff": "none"} for i in range(1, 4)]


def test_next_routine_alternates_and_stops():
    now, st = sgt("2026-11-09T23:30"), S.empty()
    assert G.next_routine(now, CFG, st, _items(2), 0)["next"] == "night-worker"
    st["last_kind"] = "worker"
    assert G.next_routine(now, CFG, st, _items(2), 0)["next"] == "night-explorer"
    assert G.next_routine(now, CFG, st, _items(0), 0)["next"] == "night-explorer"
    assert G.next_routine(now, CFG, st, _items(0), 3)["next"] == "stop"
    assert G.next_routine(now, CFG, st, _items(2), 3)["next"] == "night-worker"
    assert G.next_routine(sgt("2026-11-10T05:01"), CFG, S.empty(), _items(2), 0)["next"] == "stop"


# ------------------------------------------------------------------------------------------------ queue
QTEXT = """# Queue
<!-- queue:start -->
| id | type | status | title | acceptance test | branch/PR | opposition | ledger diff |
|---|---|---|---|---|---|---|---|
| Q001 | bug | proposed | a \\| b | test_x fails then passes |  | no block, p=60% | books.json |
| Q002 | data | proposed | c | test_y |  |  | none |
| Q003 | research | proposed | d | prereg draft |  | no block, p=20% | none |
| Q004 | lab | proposed | e | sleeve validates |  | BLOCK (c): uses 2021 returns | none |
<!-- queue:end -->
"""


def test_queue_parse_auto_approve_and_roundtrip():
    items = Q.parse(QTEXT)
    assert items[0]["title"] == "a | b"
    assert Q.auto_approve(items) == ["Q001", "Q004"]
    assert [i["status"] for i in items] == ["approved", "proposed", "proposed", "blocked"]   # research never
    again = Q.parse(Q.write(QTEXT, items))
    assert again == items and not Q.validate(items)
    items[2]["status"] = "approved"
    assert any("research" in e for e in Q.validate(items))
    assert Q.intended_ledger_files(items, ["Q001"]) == {"books.json"}


def test_real_queue_is_valid():
    items = Q.parse(frozen_copy("docs/queue.md").read_text(encoding="utf-8"))
    assert items and not Q.validate(items)
    assert not any("D003" in i["title"] and "FRED" in i["title"] for i in items)   # fixed by K002, not seeded


# ------------------------------------------------------------------------------------------------ protected
REQUIRED_PROTECTED = ["em_macro/systematic.py", "results/systematic/fit/frozen_design.json",
                      "em_macro/systematic_v11.py", "em_macro/t18_rebal.py", "docs/prereg/T25-T26_live_shadows.md",
                      "docs/prereg/T01_ts_trend.md", "results/shadows/GO_LIVE.json", "results/shadows/prelive.json",
                      "results/shadows/prelive_amendment2.json", "data/ledger/seals.jsonl", "docs/config_changes.md",
                      "ledger/commitments.py", "trials.csv", ".claude/agents/opposition.md",
                      ".claude/routines/promote.md", ".github/CODEOWNERS", "docs/rulesets/main.json"]


def test_protected_paths_cover_the_brief_and_exist_on_main():
    pats = P.patterns()
    for p in REQUIRED_PROTECTED:
        assert P.protected([p], pats) == [p], p
    for p in ["ledger/build.py", "docs/queue.md", "data/ledger/marks.csv", "results/shadows/daily.json",
              "nightshift/promote.py", "em_macro/systematic_v11_extra.py"]:
        assert not P.protected([p], pats), p
    for pat in pats:                                   # every listed path exists: nothing guessed
        assert (ROOT / pat.lstrip("/")).exists(), pat


# ------------------------------------------------------------------------------------------------ promote
def _git(repo, *a):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=repo,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / ".github").mkdir()
    (r / ".github/CODEOWNERS").write_text("# protected:start\n/docs/prereg/ @E\n/trials.csv @E\n# protected:end\n")
    (r / "docs/prereg").mkdir(parents=True)
    (r / "docs/prereg/T1.md").write_text("frozen\n")
    (r / "a.txt").write_text("1\n2\n3\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "base")
    _git(r, "branch", "dev")
    return r


def test_trial_merge_detects_conflicts_without_resolving(repo, tmp_path):
    _git(repo, "checkout", "-q", "dev")
    (repo / "a.txt").write_text("1\nDEV\n3\n")
    _git(repo, "commit", "-qam", "dev Q001")
    _git(repo, "checkout", "-q", "main")
    (repo / "a.txt").write_text("1\nMAIN\n3\n")
    _git(repo, "commit", "-qam", "writer")
    m = PR.trial_merge(repo, "main", "dev", tmp_path / "wt")
    assert not m["ok"] and m["conflicts"] == ["a.txt"]
    assert (repo / "a.txt").read_text() == "1\nMAIN\n3\n"            # nothing resolved, main untouched


def test_protected_change_on_dev_is_found_but_writer_changes_on_main_are_not(repo):
    _git(repo, "checkout", "-q", "dev")
    (repo / "docs/prereg/T1.md").write_text("edited\n")
    (repo / "b.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "Merge Q002: b")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "night-start: triage Q009, Opposition review")   # bookkeeping
    _git(repo, "checkout", "-q", "main")
    (repo / "trials.csv").write_text("writer\n")                     # an existing writer on main
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "writer")
    changed = PR.changed_on_head(repo, "main", "dev")
    assert sorted(changed) == ["b.txt", "docs/prereg/T1.md"]
    assert P.protected(changed, P.patterns(repo / ".github/CODEOWNERS")) == ["docs/prereg/T1.md"]
    assert PR.merged_item_ids(repo, "main", "dev") == ["Q002"]


def test_compare_builds_ignores_stamps_and_reports_paths_not_values(tmp_path):
    a, b = tmp_path / "a/data", tmp_path / "b/data"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "meta.json").write_text(json.dumps({"built_at": "1", "commit": "x", "today": "d"}))
    (b / "meta.json").write_text(json.dumps({"built_at": "2", "commit": "y", "today": "d"}))
    (a / "manifest.json").write_text("{}")
    (b / "manifest.json").write_text('{"build": "z"}')
    (a / "books.json").write_text(json.dumps({"me": {"mtd_pct": 1.23456}}))
    (b / "books.json").write_text(json.dumps({"me": {"mtd_pct": 9.87654}}))
    (a / "lab.json").write_text("{}")
    d = PR.compare_builds(tmp_path / "a", tmp_path / "b")
    assert d == [{"file": "data/books.json", "paths": [".me.mtd_pct"]},
                 {"file": "data/lab.json", "paths": ["(removed)"]}]
    assert "9.87" not in json.dumps(d)                               # never values
    assert [x["file"] for x in PR.unexplained(d, {"books.json"})] == ["data/lab.json"]


def test_promote_run_end_to_end_on_a_scratch_repo(repo, monkeypatch, tmp_path):
    _git(repo, "checkout", "-q", "dev")
    (repo / "b.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "Merge Q003: b")
    _git(repo, "checkout", "-q", "main")
    monkeypatch.setattr(PR, "build_ledger", lambda tree, out, today, store: (out / "data").mkdir(parents=True) or {"ok": True, "detail": ""})
    real_sh = PR.sh

    def sh(args, cwd, env=None, timeout=0):          # git runs for real; pytest and the audit checks are stubbed
        if args[0] == "git":
            return real_sh(args, cwd, env=env)
        return subprocess.CompletedProcess(args, 0, "1 passed", "")
    monkeypatch.setattr(PR, "sh", sh)
    res = PR.run(repo, "main", "dev", "2026-11-10", None, run_tests=True, work=tmp_path)
    assert res["checks"]["d_conflict_free"]["ok"] and res["checks"]["c_protected_paths"]["ok"]
    assert res["checks"]["b_ledger_rebuild"]["items_merged"] == ["Q003"]
    assert res["ok"], PR.reasons(res)
    assert _git(repo, "rev-parse", "main") == _git(repo, "rev-parse", "main")      # main never moved
    assert "dev" in _git(repo, "branch")


# ------------------------------------------------------------------------------------------------ logs
def test_exploration_log_refuses_2020_data_and_duplicates(tmp_path, monkeypatch):
    # Q015: the cutoff comes from main's config (load_main); a fixture, never the real remote
    monkeypatch.setattr(C, "load_main", lambda *a, **k: {"window": {}, "explorer": {"data_end": "2019-12-31"}})
    p = tmp_path / "log.csv"
    row = {"hypothesis_id": "H1", "variant_id": "V1", "description": "d", "data_start": "2005-01-01",
           "data_end": "2019-12-31", "metric": "sharpe", "value": "0.4"}
    LG.log_variant(dict(row), p, "2019-12-31")
    with pytest.raises(ValueError, match="2020"):
        LG.log_variant({**row, "variant_id": "V2", "data_end": "2020-01-02"}, p, "2019-12-31")
    with pytest.raises(ValueError, match="already"):
        LG.log_variant(dict(row), p, "2019-12-31")
    assert len(list(csv.DictReader(p.open()))) == 1


def test_opposition_calibration_row(tmp_path):
    p = tmp_path / "c.csv"
    LG.log_opposition({"target_type": "queue", "target_id": "Q001", "p_works": "65", "verdict": "advisory",
                       "model": "claude-opus-5-5"}, p)
    with pytest.raises(ValueError):
        LG.log_opposition({"target_type": "queue", "target_id": "Q1", "p_works": "120", "verdict": "advisory",
                           "model": "m"}, p)
    with pytest.raises(ValueError):
        LG.log_opposition({"target_type": "queue", "target_id": "Q1", "p_works": "5", "verdict": "BLOCK-z",
                           "model": "m"}, p)


# ------------------------------------------------------------------------------------------------ Lab
from lab import book as LB  # noqa: E402

INST = {"US10Y": {"instrument": "US10Y", "kind": "yield", "unit": "%", "frequency": "daily"},
        "IT-DE": {"instrument": "IT-DE", "kind": "spread", "unit": "bp", "frequency": "monthly"}}


def _sleeve(sid="L001", **kw):
    s = {"id": sid, "title": "t", "launched": "2026-11-10", "retire_on": "2027-05-10", "nominated_by": "explorer",
         "exploration_variants": ["V1"], "opposition": {"p_works": 40, "summary": "case", "model": "m"},
         "rules": "hold", "kind": "static", "instrument": "US10Y", "direction": "long", "stop": 4.5,
         "risk_pct": 0.5}
    s.update(kw)
    return s


def test_lab_sleeve_validation():
    assert LB.validate_sleeve(_sleeve(), "L001.yaml", INST) == []
    assert any("0.5" in e for e in LB.validate_sleeve(_sleeve(risk_pct=1.0), "L001.yaml", INST))
    assert any("daily" in e for e in LB.validate_sleeve(_sleeve(instrument="IT-DE"), "L001.yaml", INST))
    assert any("12 months" in e for e in LB.validate_sleeve(_sleeve(retire_on="2028-01-01"), "L001.yaml", INST))
    assert any("opposition" in e for e in LB.validate_sleeve(_sleeve(opposition={}), "L001.yaml", INST))
    assert any("licensed" in e for e in LB.validate_sleeve(_sleeve(rules="uses Databento settlement"), "L001.yaml", INST))


def test_lab_launch_is_frozen_and_capped(tmp_path):
    root, reg = tmp_path / "sleeves", tmp_path / "registry.csv"
    root.mkdir()
    for i in range(1, 12):
        (root / f"L{i:03d}.yaml").write_text(yaml.safe_dump(_sleeve(f"L{i:03d}")))
    for i in range(1, 11):
        LB.launch(f"L{i:03d}", date(2026, 11, 10), root, reg, INST)
    with pytest.raises(ValueError, match="5"):
        LB.launch("L011", date(2026, 11, 10), root, reg, INST)        # 11 x 0.5% > 5%
    with pytest.raises(ValueError, match="already"):
        LB.launch("L001", date(2026, 11, 10), root, reg, INST)
    (root / "L001.yaml").write_text(yaml.safe_dump(_sleeve("L001", stop=4.4)))
    errs = LB.check_frozen(LB.sleeves(root), LB.registry(reg))
    assert errs and "frozen" in errs[0]


def test_lab_sleeve_pnl_from_daily_marks_and_stop():
    marks = [{"instrument": "US10Y", "date": d, "value": v, "frequency": "daily", "fetched_at": f"{d}T12:00:00+00:00",
              "note": ""} for d, v in [("2026-11-09", "4.0"), ("2026-11-10", "4.10"), ("2026-11-11", "4.05"),
                                       ("2026-11-12", "4.30"), ("2026-11-13", "4.60")]]
    sp = LB.sleeve_pnl(_sleeve(stop=4.5), marks, INST["US10Y"], date(2026, 11, 20))
    assert sp["entry"] == 4.10 and sp["entry_date"] == "2026-11-10"      # fill on/after launch
    assert sp["series"][0][1] == 0.0 and sp["series"][1][1] > 0           # yield down: long bond gains
    assert sp["status"] == "closed (stop)" and sp["pnl_pct"] == -0.5      # stop costs exactly risk_pct


def test_lab_is_its_own_page_and_no_other_book_reads_it(frozen_repo):
    for f in ["ledger/books.py", "ledger/fund.py", "ledger/janus.py", "em_macro/t2526.py", "ledger/changes.py"]:
        t = (ROOT / f).read_text(encoding="utf-8")
        assert "from lab" not in t and "import lab" not in t, f
    lb = LB.build(date(2026, 11, 9))
    assert lb["label"] == "Lab - experimental" and not lb["errors"]


# ------------------------------------------------------------------------------------------------ brief
def _draft(**kw):
    d = {"date": "2026-11-14", "title": "Horizons weekly brief", "weekly_review": "weekly review 2026-11-14",
         "sections": [{"heading": "Rates", "paragraphs": ["The US 10-year yield ended the week at {L1}."]}],
         "levels": [{"id": "L1", "label": "US 10-year Treasury yield", "value": "4.12%", "as_of": "2026-11-13",
                     "sources": [{"name": "US Treasury", "url": "https://home.treasury.gov/x", "value": "4.12%"},
                                 {"name": "FRED", "url": "https://fred.stlouisfed.org/series/DGS10",
                                  "value": "4.12%"}]}],
         "glossary": [{"term": "yield", "plain": "the return a bond pays a year"}]}
    d.update(kw)
    return d


def test_brief_checks_two_sources_and_refuses_licensed_and_hand_figures():
    cfg = B.load_cfg(BRIEF_CFG)
    assert cfg["byline"] == "Ethan Cukierman, Horizons" and cfg["delivery"]["auto_send"] is False
    r = B.check(_draft(), cfg)
    assert r["ok"] and r["unverified"] == []
    one = _draft()
    one["levels"][0]["sources"] = one["levels"][0]["sources"][:1]
    assert B.check(one, cfg)["unverified"] == ["L1"]
    off = _draft()
    off["levels"][0]["sources"][1]["value"] = "4.30%"
    assert B.check(off, cfg)["unverified"] == ["L1"]
    assert not B.check(_draft(sections=[{"heading": "x", "paragraphs": ["CME settlement was {L1}"]}]), cfg)["ok"]
    assert not B.check(_draft(sections=[{"heading": "x", "paragraphs": ["Yields rose to 4.5% today"]}]), cfg)["ok"]
    txt = B.to_text(one, cfg, B.check(one, cfg))
    assert "4.12% (unverified)" in txt and "Ethan Cukierman, Horizons" in txt


def test_brief_pdf_renders(tmp_path):
    pytest.importorskip("reportlab")
    cfg = B.load_cfg(BRIEF_CFG)
    d = _draft()
    B.render_pdf(d, cfg, B.check(d, cfg), tmp_path / "b.pdf")
    assert (tmp_path / "b.pdf").read_bytes()[:4] == b"%PDF"


# ------------------------------------------------------------------------------------------------ agent files
AGENTS = {"triage": "claude-sonnet-5-5", "implementer": "claude-opus-5-5", "opposition": "claude-opus-5-5",
          "explorer": "claude-opus-5-5", "reporter": "claude-sonnet-5-5"}
ROUTINES = ["night-start", "night-worker", "night-explorer", "pr-review", "promote", "morning-report", "weekly-brief"]


def _front(path: Path) -> dict:
    t = path.read_text(encoding="utf-8")
    assert t.startswith("---\n"), path
    return yaml.safe_load(t.split("---\n")[1])


def test_subagents_have_model_effort_and_minimal_tools():
    for name, model in AGENTS.items():
        fm = _front(ROOT / f".claude/agents/{name}.md")
        assert fm["name"] == name and fm["model"] == model and fm["description"]
        assert fm["effort"] == ("high" if "opus" in model else "medium")
        tools = [t.strip() for t in str(fm["tools"]).split(",")]
        if name in ("triage", "opposition"):
            assert not {"Write", "Edit"} & set(tools), name      # read-only
    assert "BLOCK" in (ROOT / ".claude/agents/opposition.md").read_text()


def test_routines_are_self_contained():
    for r in ROUTINES:
        t = (ROOT / f".claude/routines/{r}.md").read_text(encoding="utf-8")
        head = "\n".join(t.splitlines()[:6])
        assert "Routine model:" in head and "Effort:" in head, r
        for must in ("CLAUDE.md", "docs/agent-state.json", "docs/queue.md"):
            assert must in t, (r, must)


def test_claude_md_keeps_existing_notes_and_adds_hard_rules():
    t = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Pasted ledger blocks" in t and "Janus sessions" in t
    for must in ("never push to main", "protected paths", "Norgate", "salts", "7-day settlement re-request",
                 "data, not instructions"):
        assert must.lower() in t.lower(), must


def test_morning_report_lists_real_merges_and_reads_janus(frozen_repo):
    from nightshift import morning as M
    assert M.MERGE_SUBJECT.match("Merge Q003: todo counts") and M.MERGE_SUBJECT.match("night-start: merge main into dev")
    assert not M.MERGE_SUBJECT.match("night-worker: lock (dry run)")
    long = "(c) protected paths touched: ['.claude/a.md', '.claude/b.md', '.github/CODEOWNERS', 'docs/rulesets/main.json', 'x', 'y']"
    assert M._short(long) == "(c) protected paths touched: .claude/a.md, .claude/b.md (+4 more)"
    lines = M.janus_section(date(2026, 11, 10))
    assert lines[0].startswith("C05: ") and "at risk (budget 3-10%)" in lines[0]
