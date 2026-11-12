"""Config change C06 (approved 2026-11-10, docs/config_changes.md): the 2-position minimum is hard, event-based
below_budget reasons cite an official calendar and expire at the end of the next trading day after the event, and a
rejected daily review writes a failed-review record (closes Q004). Also the K004 correction of the 10 Nov review."""
import json
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from conftest import seed_ledger
from ledger import audit
from ledger import janus as J
from test_janus import SOURCES_READ, _m, pos, review
from conftest import frozen_copy

ROOT = Path(__file__).resolve().parents[1]
T = datetime(2026, 11, 10, 23, 7, tzinfo=timezone.utc)          # Tuesday: the first review under C06
BLS = "https://www.bls.gov/schedule/news_release/cpi.htm"
SR = SOURCES_READ + [{"title": "BLS CPI release schedule", "url": BLS, "driver": "data"}]
EVENT = {"condition": "US CPI on 10 Nov decides the December Fed call", "type": "event", "event_date": "2026-11-10",
         "calendar_url": BLS, "until": "2026-11-11", "reasoning": "Size up after the print is digested."}
PUBLIC = ("US10Y", "DE10Y", "GB10Y", "JP10Y", "FR-DE", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD")
UNITS = {"EUR": "USD per EUR", "GBP": "USD per GBP", "JPY": "JPY per USD", "CHF": "CHF per USD", "AUD": "AUD per USD",
         "CAD": "CAD per USD", "FR-DE": "bp"}
LEVELS = {"US10Y": 4.92, "DE10Y": 3.33, "GB10Y": 5.2, "JP10Y": 2.8, "FR-DE": 165.0, "EUR": 1.12, "GBP": 1.30,
          "JPY": 158.0, "CHF": 0.82, "AUD": 1.43, "CAD": 1.40}


def marks(d="2026-11-09", stale=()):
    """Every public Janus instrument marked on ``d``; those in ``stale`` last marked on 2026-11-04."""
    return [_m(i, "2026-11-04" if i in stale else d, LEVELS[i], UNITS.get(i, "% yield")) for i in PUBLIC]


@pytest.fixture(autouse=True)
def no_store(tmp_path, monkeypatch):
    """No private settlements: the 11 futures markets have no mark (as in a session without em-macro-data)."""
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path / "no-store"))


@pytest.fixture(autouse=True)
def before_c08(monkeypatch):
    """Config change C08 (11 Nov 2026, tests/test_janus_c08.py) replaced discretionary selection, superseding C06 rules
    1-2. These tests keep the C06 code tested as it ran before C08, with C08 switched off for the dates they use."""
    monkeypatch.setattr(J, "C08_FROM", date(2099, 1, 1))


TWO = [pos(instrument="US10Y", stop=5.10, risk_pct=0.25), pos(instrument="DE10Y", stop=3.50, risk_pct=0.25)]


def c06(**over):
    return review(**{"new_positions": TWO, "sources_read": SR, "below_budget": EVENT, **over})


CPI_UTC = datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc)      # 08:30 ET (BLS)
FILLERS = [("EUR", "long"), ("GOLD", "long"), ("WTI", "short"), ("JPY", "long"), ("AUD", "short")]


def c07_fields(ans, now):
    """Config change C07 (tested in test_janus_c07.py) applies to these reviews too: a time anchor and, when the
    two-position minimum binds, at least 5 candidates across 2 asset classes. Added only where a proposal has none."""
    ans = dict(ans)
    ans.setdefault("time_anchor", {"now_utc": now.isoformat(), "events": [
        {"event": "US October CPI (BLS)", "time_utc": CPI_UTC.isoformat(), "occurred": now >= CPI_UTC}]})
    if "candidates" not in ans:
        c = [{"instrument": n["instrument"], "direction": n["direction"], "probability": n["probability"],
              "market_probability": 50, "outcome": "opened", "opposition": "kept", "reason": "the best idea in the search"}
             for n in ans.get("new_positions") or []]
        c += [{"instrument": d["instrument"], "direction": d["direction"], "probability": d["probability"],
               "market_probability": 50, "outcome": "deferred", "opposition": "none", "reason": "its market is closed"}
              for d in ans.get("deferred_ideas") or []]
        have = {x["instrument"] for x in c}
        c += [{"instrument": i, "direction": d, "probability": 52, "market_probability": 50, "outcome": "not_opened",
               "opposition": "none", "reason": "a smaller edge than the ideas taken"} for i, d in FILLERS if i not in have]
        ans["candidates"] = c
    return ans


def run(tmp_path, ans, now=T, mk=None, name="r.jsonl"):
    return J.apply_proposal(c07_fields(ans, now), now=now, path=tmp_path / name, marks_rows=marks() if mk is None else mk)


# ----------------------------------------------------------------------------- rule 1: at least 2 positions
def test_two_small_positions_with_a_dated_event_reason_pass(tmp_path):
    res = run(tmp_path, c06())
    assert res["ok"], res["errors"]
    rec = [r for r in J.load(tmp_path / "r.jsonl") if r["type"] == "run"][-1]
    assert rec["risk_after_pct"] == 0.5 and rec["below_budget"]["event_date"] == "2026-11-10"


@pytest.mark.parametrize("new", [[], [pos(instrument="US10Y", stop=5.10, risk_pct=0.25)]])
def test_below_budget_can_never_take_the_book_below_two_positions(tmp_path, new):
    res = run(tmp_path, c06(new_positions=new, no_trade_reasoning="Waiting for the CPI print."))
    assert not res["ok"] and any("C06 requires at least 2" in e and "never the number of positions" in e
                                 for e in res["errors"]), res["errors"]


def test_closing_to_one_position_is_rejected(tmp_path):
    assert run(tmp_path, c06())["ok"]
    res = run(tmp_path, c06(new_positions=[], no_trade_reasoning="x",
                            reviews=[{"id": "J001", "action": "close", "reasoning": "done"},
                                     {"id": "J002", "action": "hold", "reasoning": "on track"}]))
    assert not res["ok"] and any("would hold 1 position" in e for e in res["errors"]), res["errors"]


def test_minimum_applies_from_c06_only():
    """A one-position review on 9 Nov (before C06) still passes, so earlier behaviour is unchanged."""
    res = J.apply_proposal(review(sources_read=SR), now=datetime(2026, 11, 9, 23, 7, tzinfo=timezone.utc),
                           path=None, marks_rows=marks("2026-11-06"))
    assert res["ok"], res["errors"]


DF = {"condition": "The official marks feed has failed for every public instrument (see data_failure)",
      "type": "condition", "until": "2026-11-12", "reasoning": "No current mark to enter or stop a position on."}


def test_data_failure_excuses_only_the_instruments_affected(tmp_path):
    ans = c06(new_positions=[], no_trade_reasoning="Marks are stale.", below_budget=DF,
              data_failure=[{"instrument": "GB10Y", "mark": "BoE gilt 10y daily yield", "last_mark": "2026-11-04"}])
    res = run(tmp_path, ans, mk=marks(stale=("GB10Y",)))
    assert not res["ok"] and any("covers only GB10Y" in e and "open at least 2 position(s) there" in e
                                 for e in res["errors"]), res["errors"]


@pytest.mark.parametrize("entry, expect", [
    ({"instrument": "US10Y", "mark": "FRED DGS10", "last_mark": "2026-11-09"}, "is current"),
    ({"instrument": "US10Y", "mark": "FRED DGS10", "last_mark": "2026-11-02"}, "does not match its latest mark"),
    ({"instrument": "US10Y", "mark": "", "last_mark": "2026-11-04"}, "mark is required"),
    ({"instrument": "US10Y", "mark": "FRED DGS10"}, "last_mark is required"),
    ({"instrument": "PLATINUM", "mark": "x", "last_mark": "none"}, "not in the universe"),
])
def test_data_failure_must_be_named_and_real(tmp_path, entry, expect):
    ans = c06(new_positions=[], no_trade_reasoning="x", below_budget=DF, data_failure=[entry])
    res = run(tmp_path, ans, mk=marks(stale=() if "is current" in expect else PUBLIC))
    assert not res["ok"] and any(expect in e for e in res["errors"]), res["errors"]


def test_a_real_data_failure_across_the_universe_allows_fewer_than_two(tmp_path):
    df = [{"instrument": i, "mark": "official daily mark", "last_mark": "2026-11-04"} for i in PUBLIC]
    df += [{"instrument": i, "mark": "Databento final settlement (em-macro-data)", "last_mark": "none"}
           for i in J.UNIVERSE if J.is_future(i)]
    df += [{"instrument": i, "mark": "central-bank fixing (no mark in this test)", "last_mark": "none"}
           for i in J.UNIVERSE if not J.is_future(i) and i not in PUBLIC]            # BRL, MXN (added by C09)
    res = run(tmp_path, c06(new_positions=[], no_trade_reasoning="No current marks.", below_budget=DF,
                            data_failure=df), mk=marks(stale=PUBLIC))
    assert res["ok"], res["errors"]
    rec = [r for r in J.load(tmp_path / "r.jsonl") if r["type"] == "run"][-1]
    assert len(rec["data_failure"]) == len(J.UNIVERSE)


def test_weekend_deferred_ideas_count_toward_the_minimum(tmp_path):
    sat = datetime(2026, 11, 14, 23, 7, tzinfo=timezone.utc)
    ideas = [{"instrument": i, "direction": "long", "risk_pct": 1.5, "probability": 57, "market_probability": 50,
              "thesis": "Enter at Monday's mark."} for i in ("US10Y", "DE10Y")]
    res = run(tmp_path, c06(new_positions=[], no_trade_reasoning="Weekend.", below_budget=None, deferred_ideas=ideas),
              now=sat, mk=marks("2026-11-13"))
    assert res["ok"], res["errors"]
    res = run(tmp_path, c06(new_positions=[], no_trade_reasoning="Weekend.", below_budget=None,
                            deferred_ideas=[{**ideas[0], "risk_pct": 2.0}, {**ideas[1], "risk_pct": 1.0}][:1]),
              now=sat, mk=marks("2026-11-13"), name="one.jsonl")
    assert not res["ok"] and any("C06 requires at least 2" in e for e in res["errors"])


# ----------------------------------------------------------------------------- rule 2: event-based reasons
@pytest.mark.parametrize("bb, sr, expect", [
    ({**EVENT, "event_date": None}, SR, "event_date (YYYY-MM-DD) is required"),
    ({**EVENT, "calendar_url": "https://www.forexfactory.com/calendar"},
     SR + [{"title": "ff", "url": "https://www.forexfactory.com/calendar"}], "must be the official calendar"),
    ({**EVENT, "calendar_url": None}, SR, "must be the official calendar"),
    (EVENT, SOURCES_READ, "must also be listed in sources_read"),
    ({**EVENT, "until": "2026-11-13"}, SR, "expires at the end of the next trading day after the event (2026-11-11)"),
    ({**EVENT, "condition": "US CPI on 12 Nov decides the December Fed call"}, SR, "dates the event differently"),
    ({**EVENT, "event_date": "2026-11-06", "until": "2026-11-10"}, SR, "expired at the end of 2026-11-09"),
    ({k: v for k, v in EVENT.items() if k not in ("type", "event_date", "calendar_url")}, SR, "tied to an event"),
])
def test_event_reason_cites_an_official_calendar_and_expires(tmp_path, bb, sr, expect):
    res = run(tmp_path, c06(below_budget=bb, sources_read=sr))
    assert not res["ok"] and any(expect in e for e in res["errors"]), res["errors"]


def test_event_expiry_is_the_end_of_the_next_trading_day():
    assert J.next_trading_day(date(2026, 11, 10)) == date(2026, 11, 11)
    assert J.next_trading_day(date(2026, 11, 13)) == date(2026, 11, 16)          # Friday event: Monday
    assert J.official_calendar(BLS) and J.official_calendar("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    assert not J.official_calendar("https://www.investing.com/economic-calendar/")
    assert not J.official_calendar("https://bls.gov.example.com/cpi")


def test_budget_status_expires_an_event_reason(tmp_path):
    path = tmp_path / "r.jsonl"
    one = [pos(instrument="US10Y", stop=5.10, risk_pct=0.25), pos(instrument="DE10Y", stop=3.50, risk_pct=0.25)]
    assert run(tmp_path, c06(new_positions=one))["ok"]
    recs = J.load(path)
    assert "reason" in J.budget_status(recs, date(2026, 11, 11))
    fl = J.budget_status(recs, date(2026, 11, 12))["flags"]
    assert fl and "below the 3% budget without a current specific reason" in fl[0] and "expired at the end of 2026-11-11" in fl[0]


# ----------------------------------------------------------------------------- rule 3: failed-review record (Q004)
def test_rejected_review_writes_a_failed_record_the_quick_check_flags(tmp_path):
    path = tmp_path / "r.jsonl"
    res = run(tmp_path, c06(new_positions=[], no_trade_reasoning="Waiting for CPI."))
    assert not res["ok"] and res["failed_record"] == 1
    recs = J.load(path)
    assert len(recs) == 1 and J.verify(recs)["ok"]
    rec = recs[0]
    assert (rec["type"], rec["session"], rec["status"], rec["date"]) == ("run", "daily_review", "failed", "2026-11-10")
    assert any("C06 requires at least 2" in e for e in rec["errors"]) and rec["sources_read"] == SR
    assert len(rec["proposal_sha256"]) == 64
    st = J.review_status(recs, date(2026, 11, 10))
    assert st["status"] == "failed" and "rejected by the CLI" in st["flags"][0]
    chk = J.record_check(["none"], "no change", "claude-opus-5-5", now=datetime(2026, 11, 10, 23, 45, tzinfo=timezone.utc),
                         path=path)
    assert any("daily review 2026-11-10 failed: rejected by the CLI" in f for f in chk["flags"])
    assert J.summarize(J.load(path), marks(), date(2026, 11, 10))["runs"][0]["status"] == "failed"
    # the fixed review passes and clears the flag
    assert run(tmp_path, c06())["ok"]
    assert J.review_status(J.load(path), date(2026, 11, 11))["status"] == "ok"


def test_dry_run_and_quick_checks_write_no_failed_record(tmp_path):
    path = tmp_path / "r.jsonl"
    res = J.apply_proposal(c06(new_positions=[], no_trade_reasoning="x"), now=T, path=path, marks_rows=marks(),
                           dry_run=True)
    assert not res["ok"] and not path.exists()
    res = J.apply_proposal({"session": "quick_check", "model": "m", "reviews": []}, now=T, path=path, marks_rows=marks())
    assert not res["ok"] and not path.exists()


def test_failed_record_withholds_futures_error_details():
    assert "withheld" not in J._public_error("C06 requires at least 2")
    e = J._public_error("new position 1 (WTI): capacity: the most this stop allows is 0.37% at risk")
    assert "0.37" not in e and e.startswith("new position 1 (WTI)")
    assert "94" not in J._public_error("J003: new stop 94 is already through the latest settlement")


def test_cli_exits_3_after_writing_the_failed_record(tmp_path, monkeypatch, capsys):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(c06(new_positions=[], no_trade_reasoning="x")))
    real = J.apply_proposal
    monkeypatch.setattr(J.ST, "ensure_read_only_store", lambda: (None, "test: no store"))
    monkeypatch.setattr(J.ST, "_PROCESS_READ_ONLY", False)       # main() sets it; restored after the test
    monkeypatch.setattr(J, "apply_proposal", lambda ans, dry_run=False: real(
        ans, now=T, path=tmp_path / "r.jsonl", marks_rows=marks(), dry_run=dry_run))
    assert J.main(["propose", "--file", str(f), "--dry-run"]) == 1 and not (tmp_path / "r.jsonl").exists()
    assert J.main(["propose", "--file", str(f)]) == 3
    assert "failed-review record 1" in capsys.readouterr().err


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def test_ledger_commit_pushes_the_failed_record_and_exits_3(tmp_path):
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    work.mkdir()
    for d in ("ledger", "scripts"):
        shutil.copytree(ROOT / d, work / d, ignore=shutil.ignore_patterns("__pycache__", "site"))
    seed_ledger(work)
    (work / "data/janus").mkdir(parents=True)
    (work / ".gitignore").write_text("__pycache__/\n")
    _git("init", "-q", "-b", "test", cwd=work)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A", cwd=work)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init", cwd=work)
    _git("init", "-q", "--bare", str(origin), cwd=tmp_path)
    _git("remote", "add", "origin", str(origin), cwd=work)
    _git("push", "-q", "origin", "test", cwd=work)
    _git("config", "user.name", "t", cwd=work)
    _git("config", "user.email", "t@t", cwd=work)
    rejected = ("import sys; from ledger import janus as J; "
                "J.append(J.load(), {'type': 'run', 'session': 'daily_review', 'date': '2026-11-10', 'status': 'failed', "
                "'errors': ['x'], 'model': 'm'}); sys.exit(3)")
    env = {**__import__("os").environ, "LEDGER_BRANCH": "test", "EM_MACRO_DATA": str(tmp_path / "no-store")}
    p = subprocess.run(["bash", "scripts/ledger_commit.sh", "Janus daily review", "--", sys.executable, "-c", rejected],
                       cwd=work, capture_output=True, text=True, env=env)
    assert p.returncode == 3, p.stdout + p.stderr
    _git("fetch", "-q", "origin", cwd=work)
    assert "REJECTED: failed-review record" in _git("log", "-1", "--format=%s", "origin/test", cwd=work)
    recs = [json.loads(x) for x in _git("show", "origin/test:data/janus/records.jsonl", cwd=work).splitlines()]
    assert [r["status"] for r in recs] == ["failed"]
    # any other failure still commits nothing
    p = subprocess.run(["bash", "scripts/ledger_commit.sh", "x", "--", sys.executable, "-c", "import sys; sys.exit(1)"],
                       cwd=work, capture_output=True, text=True, env=env)
    assert p.returncode == 1 and "nothing committed" in p.stderr


# ----------------------------------------------------------------------------- K004: the 10 Nov review
def _janus_until(seq):
    out = []
    for line in frozen_copy("data/janus/records.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["seq"] > seq:
            break
        out.append(r)
    return out


def test_10_nov_review_reason_expires_at_the_end_of_11_nov():
    recs = _janus_until(199)                    # the chain as it stood after the 10 Nov 07:05 UTC review
    last = recs[-1]
    assert (last["seq"], last["date"], last["below_budget"]["until"]) == (199, "2026-11-10", "2026-11-13")
    assert J.verify(recs)["ok"]                 # the record is not edited
    assert J.reason_expiry(last) == (date(2026, 11, 11), "C06, correction K004")
    assert "reason" in J.budget_status(recs, date(2026, 11, 11))
    fl = J.budget_status(recs, date(2026, 11, 12))["flags"]
    assert fl and "expired at the end of 2026-11-11" in fl[0] and "K004" in fl[0]


def test_janus_correction_annotates_without_editing(tmp_path, frozen_repo):
    seed_ledger(tmp_path)
    seals = tmp_path / "data/ledger/seals.jsonl"
    shutil.copy(ROOT / "tests/fixtures/ledger/decisions.csv", tmp_path / "data/ledger/decisions.csv")
    jp = tmp_path / "records.jsonl"
    shutil.copy(frozen_copy("data/janus/records.jsonl"), jp)
    rec = audit.correct_janus(199, {"below_budget.until": "2026-11-11 (C06)"}, "CPI is on 10 Nov", path=seals,
                              janus_path=jp, now="2026-11-10T12:00:00+00:00")
    assert rec["kind"] == "janus" and rec["record_edited"] is False and rec["janus_seq"] == 199
    assert rec["fields"]["below_budget.until"] == {"old": "2026-11-13", "new": "2026-11-11 (C06)"}
    assert audit.verify_seals(seals, jp)["ok"]
    with pytest.raises(ValueError, match="no field"):
        audit.correct_janus(199, {"below_budget.nope": "x"}, "r", path=seals, janus_path=jp)
    lines = jp.read_text().splitlines()
    r199 = json.loads(lines[198])
    r199["below_budget"]["until"] = "2026-11-11"
    lines[198] = json.dumps(r199)
    jp.write_text("\n".join(lines) + "\n")
    assert not audit.verify_seals(seals, jp)["ok"]           # the record may never be edited


def test_k004_is_in_the_corrections_log():
    seals = [json.loads(x) for x in frozen_copy("data/ledger/seals.jsonl").read_text().splitlines() if x.strip()]
    k4 = [s for s in seals if s.get("correction_id") == "K004"]
    assert len(k4) == 1 and k4[0]["kind"] == "janus" and k4[0]["janus_seq"] == 199
    f = k4[0]["fields"]
    assert "10 Nov 2026, 08:30 ET" in f["below_budget.condition"]["new"] and BLS in f["below_budget.condition"]["new"]
    assert f["below_budget.until"]["old"] == "2026-11-13" and "2026-11-11" in f["below_budget.until"]["new"]
    assert J.BELOW_BUDGET_EXPIRY_CORRECTIONS[k4[0]["janus_hash"]] == ("K004", date(2026, 11, 11))
