"""Janus (ledger/janus.py): the propose -> validate -> append CLI, fills, stops, costs and the hash chain.
No API is called: proposals are written by Claude Code sessions (docs/janus/)."""
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from ledger import janus as J
from ledger import pricing as PX

ROOT = Path(__file__).resolve().parents[1]


def _m(inst, d, v, unit="% yield", freq="daily", note=""):
    return {"date": d, "instrument": inst, "value": str(v), "unit": unit, "frequency": freq, "source": "test",
            "source_url": "https://example.org", "fetched_at": f"{d}T06:00:00+00:00", "note": note}


MARKS = [_m("US10Y", "2026-11-04", 4.90), _m("US10Y", "2026-11-05", 4.92), _m("WTI", "2026-11-03", 100.0, "USD per bbl"),
         _m("EUR", "2026-11-05", 1.12, "USD per EUR"), _m("JPY", "2026-11-05", 158.0, "JPY per USD"),
         _m("NATGAS", "2026-11-03", 2.6, "USD per MMBtu"), _m("DE10Y", "2026-11-05", 3.33), _m("GB10Y", "2026-11-05", 5.2),
         _m("JP10Y", "2026-11-05", 2.8), _m("CHF", "2026-11-05", 0.82, "CHF per USD"), _m("CAD", "2026-11-05", 1.40, "CAD per USD"),
         _m("AUD", "2026-11-05", 1.43, "AUD per USD")]
NOW = datetime(2026, 11, 6, 22, 7, tzinfo=timezone.utc)
OPP = {"case_against": "Inflation is sticky and the Fed leans to hikes.", "key_risks": ["CPI"],
       "what_proves_it_wrong": "Core CPI above 0.4% m/m", "probability_view_wrong": 55, "model": "claude-opus-5-5"}


def pos(**over):
    p = {"instrument": "US10Y", "direction": "long", "risk_pct": 1.0, "stop": 5.10, "horizon": "2026-12-18",
         "probability": 60, "thesis": "Growth is slowing as oil falls. Yields should drift lower into December.",
         "change_mind": "Payrolls above 250k or core CPI above 0.4% m/m.",
         "sources": [{"title": "Fed statement", "url": "https://www.federalreserve.gov/x"}], "opposition": OPP,
         "market_probability": 50, "market_basis": "none",
         "market_source": "no market-implied probability for a 10y yield move to this level: coin flip (0.50)"}
    p.update(over)
    return p


SOURCES_READ = [{"title": "FOMC statement", "url": "https://www.federalreserve.gov/s"},
                {"title": "CFTC Commitments of Traders", "url": "https://www.cftc.gov/cot"}]
BELOW = {"condition": "US CPI release on 12 Nov decides the December Fed call; sizing up before it is a coin toss",
         "until": "2026-11-18", "reasoning": "Add the rates ideas after the CPI print."}


def review(**over):
    p = {"session": "daily_review", "model": "claude-opus-5-5", "market_summary": "Rates elevated.", "reviews": [],
         "new_positions": [pos()], "no_trade_reasoning": "", "sources_read": SOURCES_READ, "below_budget": BELOW}
    p.update(over)
    return p


def test_valid_daily_review_opens_with_opposition_and_entry_at_next_mark(tmp_path):
    path = tmp_path / "r.jsonl"
    res = J.apply_proposal(review(), now=NOW, path=path, marks_rows=MARKS)
    assert res["ok"] and res["opened"] == ["J001"]
    recs = J.load(path)
    assert [r["type"] for r in recs] == ["account_open", "run", "open", "opposition"]
    o = recs[2]
    assert o["model"] == "claude-opus-5-5" and o["session"] == "daily_review" and o["decision_date"] == "2026-11-06"
    assert recs[3]["opposition"]["case_against"].startswith("Inflation")
    assert J.positions(recs)["J001"]["status"] == "pending"         # fills only at the next official daily mark
    assert J.verify(recs)["ok"]


@pytest.mark.parametrize("bad, expect", [
    (dict(new_positions=[pos(risk_pct=2.5)]), "above the 2% per-position limit"),
    (dict(new_positions=[pos(instrument="PLATINUM")]), "not in the universe"),
    (dict(new_positions=[pos(stop=4.70)]), "not on the losing side"),
    (dict(new_positions=[pos(thesis="Yields fall.")]), "2-3 sentences"),
    (dict(new_positions=[pos(thesis="One. Two. Three. Four.")]), "2-3 sentences"),
    (dict(new_positions=[pos(change_mind="")]), "change_mind"),
    (dict(new_positions=[pos(sources=[])]), "source with a URL"),
    (dict(new_positions=[pos(opposition={})]), "The Opposition is required"),
    (dict(new_positions=[pos(horizon="2026-11-08")]), "horizon"),
    (dict(new_positions=[pos(probability=0)]), "probability"),
    (dict(new_positions=[pos(direction="up")]), "direction"),
    (dict(new_positions=[pos(instrument="NATGAS", stop=2.0, risk_pct=2.0)]), "no private settlement"),   # see test_janus_futures
    (dict(new_positions=[], no_trade_reasoning=""), "no_trade_reasoning is required"),
    (dict(model=""), "model is required"),
    (dict(session="weekly"), "session must be one of"),
])
def test_rule_breaking_proposals_are_rejected_whole(tmp_path, bad, expect):
    path = tmp_path / "r.jsonl"
    res = J.apply_proposal(review(**bad), now=NOW, path=path, marks_rows=MARKS)
    assert not res["ok"] and any(expect in e for e in res["errors"]), res["errors"]
    if bad.get("session") == "weekly":
        assert not path.exists()                                   # not a daily review: nothing appended
    else:                                                          # C06: only a failed-review record, nothing applied
        assert [(r["type"], r["status"]) for r in J.load(path)] == [("run", "failed")]


def test_total_risk_and_position_count_limits(tmp_path):
    path = tmp_path / "r.jsonl"
    six = [pos(instrument=i, risk_pct=2.0, stop=s, direction=d) for i, s, d in
           (("US10Y", 5.10, "long"), ("DE10Y", 3.50, "long"), ("GB10Y", 5.40, "long"), ("JP10Y", 3.0, "long"),
            ("EUR", 1.10, "long"), ("JPY", 165.0, "long"))]
    res = J.apply_proposal(review(new_positions=six), now=NOW, path=path, marks_rows=MARKS)
    assert not res["ok"] and any("above the 10% limit" in e and "room: 0.00%" in e for e in res["errors"])
    small = [pos(instrument=i, risk_pct=0.5, stop=s, direction="long") for i, s in
             (("US10Y", 5.10), ("DE10Y", 3.50), ("GB10Y", 5.40), ("JP10Y", 3.0), ("EUR", 1.10), ("JPY", 165.0),
              ("CHF", 0.86), ("CAD", 1.45), ("AUD", 1.50))]
    res = J.apply_proposal(review(new_positions=small), now=NOW, path=path, marks_rows=MARKS)
    assert not res["ok"] and any("at most 8 may be open" in e for e in res["errors"])
    assert J.apply_proposal(review(new_positions=small[:8]), now=NOW, path=path, marks_rows=MARKS)["ok"]


def test_daily_review_must_review_every_open_position_and_stops_only_tighten(tmp_path):
    path = tmp_path / "r.jsonl"
    J.apply_proposal(review(), now=NOW, path=path, marks_rows=MARKS)
    later = datetime(2026, 11, 9, 22, 7, tzinfo=timezone.utc)
    nt = dict(new_positions=[], no_trade_reasoning="Nothing new clears the bar.")
    res = J.apply_proposal(review(**nt), now=later, path=path, marks_rows=MARKS)
    assert not res["ok"] and any("missing J001" in e for e in res["errors"])
    res = J.apply_proposal(review(reviews=[{"id": "J001", "action": "hold", "reasoning": ""}], **nt), now=later, path=path, marks_rows=MARKS)
    assert not res["ok"] and any("reason is required" in e for e in res["errors"])
    res = J.apply_proposal(review(reviews=[{"id": "J001", "action": "tighten_stop", "new_stop": 5.30, "reasoning": "x"}], **nt),
                           now=later, path=path, marks_rows=MARKS)
    assert not res["ok"] and any("can only be tightened" in e for e in res["errors"])
    res = J.apply_proposal(review(reviews=[{"id": "J001", "action": "tighten_stop", "new_stop": 5.0, "reasoning": "data"}], **nt),
                           now=later, path=path, marks_rows=MARKS)
    assert res["ok"]
    recs = J.load(path)
    assert J.positions(recs)["J001"]["stop"] == 5.0 and recs[-1]["type"] == "no_trade"


def test_quick_check_rules_and_check_records(tmp_path):
    path = tmp_path / "r.jsonl"
    J.apply_proposal(review(), now=NOW, path=path, marks_rows=MARKS)
    qc = {"session": "quick_check", "model": "claude-opus-5-5", "new_positions": [pos(instrument="EUR", stop=1.10)]}
    res = J.apply_proposal(qc, now=NOW, path=path, marks_rows=MARKS)
    assert not res["ok"] and any("cannot open positions" in e for e in res["errors"])
    res = J.apply_proposal({"session": "quick_check", "model": "m", "reviews": []}, now=NOW, path=path, marks_rows=MARKS)
    assert not res["ok"] and any("record a check" in e for e in res["errors"])
    with pytest.raises(ValueError, match="every open position"):
        J.record_check(["none"], "no change", "claude-opus-5-5", now=NOW, path=path)
    with pytest.raises(ValueError, match="not open"):
        J.record_check(["J001", "J009"], "no change", "claude-opus-5-5", now=NOW, path=path)
    rec = J.record_check(["J001"], "no change", "claude-opus-5-5", now=NOW, path=path)
    assert rec["type"] == "check" and rec["positions"] == ["J001"]
    res = J.apply_proposal({"session": "quick_check", "model": "m", "reviews": [
        {"id": "J001", "action": "close", "reasoning": "Payrolls printed 300k: the thesis trigger fired."}]},
        now=NOW, path=path, marks_rows=MARKS)
    assert res["ok"]
    s = J.summarize(J.load(path), MARKS, date(2026, 11, 6))
    assert s["last_check"]["session"] == "quick_check" and "next official daily mark" in s["fill_rule"]
    assert J.positions(J.load(path))["J001"]["status"] == "cancelled"   # closed before its fill


def test_fill_stop_close_and_costs(tmp_path):
    path = tmp_path / "r.jsonl"
    J.apply_proposal(review(), now=datetime(2026, 11, 6, 10, tzinfo=timezone.utc), path=path, marks_rows=MARKS)
    recs = J.load(path)
    marks = MARKS + [_m("US10Y", "2026-11-06", 4.95), _m("US10Y", "2026-11-09", 5.00), _m("US10Y", "2026-11-10", 5.12)]
    J.process(recs, MARKS, date(2026, 11, 6), path)                  # marks before the decision date never fill
    assert J.positions(recs)["J001"]["status"] == "pending"
    J.process(recs, marks[:-2], date(2026, 11, 7), path)
    p = J.positions(recs)["J001"]
    assert p["status"] == "open" and p["fill"]["entry_level"] == 4.95 and p["fill"]["cost_pct"] > 0
    assert p["fill"]["notional_frac"] == pytest.approx(0.01 / abs(PX.stop_return("yield", "long", 4.95, 5.10)))
    J.process(recs, marks, date(2026, 11, 10), path)
    c = J.positions(recs)["J001"]["close"]
    assert c["reason"] == "stop" and c["outcome"] == "wrong" and c["net_pnl_pct"] < c["gross_pnl_pct"] < -1.0
    assert J.verify(recs)["ok"]


def test_monthly_or_carried_marks_never_fill(tmp_path):
    path = tmp_path / "r.jsonl"
    J.apply_proposal(review(), now=NOW, path=path, marks_rows=MARKS)
    recs = J.load(path)
    J.process(recs, MARKS + [_m("US10Y", "2026-11-30", 4.8, freq="monthly"),
                             _m("US10Y", "2026-11-09", 4.9, note="kept previous mark; down")], date(2026, 12, 1), path)
    assert J.positions(recs)["J001"]["status"] == "pending"


def test_hash_chain_detects_an_edit(tmp_path):
    path = tmp_path / "r.jsonl"
    J.apply_proposal(review(new_positions=[], no_trade_reasoning="x"), now=NOW, path=path, marks_rows=MARKS)
    recs = J.load(path)
    assert J.verify(recs)["ok"]
    recs[1]["status"] = "edited"
    assert not J.verify(recs)["ok"]
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    assert not J.apply_proposal(review(), now=NOW, path=path, marks_rows=MARKS)["ok"]   # refuses a broken chain


def test_commodity_roll_rule_and_capacity_cap():
    assert J.front_contract("WTI", date(2026, 11, 6))["code"] == "CLF27"
    from ledger import capacity as CAP
    sz = J.size("NATGAS", "long", 2.0, 2.6, 2.0, J.registry_rows(), CAP.load_reference())
    assert sz["capacity_note"] and sz["risk_pct"] < 2.0 and sz["capacity"]["pct_adv"] <= CAP.MAX_PCT_ADV + 1e-6
    assert J.calls_needed(0.6) == 153 and J.calls_needed(0.5) is None


def test_cli_rejects_a_bad_proposal_with_exit_1(tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(review(new_positions=[pos(risk_pct=5)])))
    # an isolated private store: the CLI never clones the real em-macro-data from a test
    env = {**__import__("os").environ, "EM_MACRO_DATA": str(tmp_path / "no-store"),
           "DATA_REPO_URL": str(tmp_path / "no-such-repo.git")}
    env.pop("DATA_REPO_READ_TOKEN", None)
    out = subprocess.run([sys.executable, "-m", "ledger.janus", "propose", "--file", str(f), "--dry-run"], cwd=ROOT,
                         capture_output=True, text=True, env=env)
    # the CLI's clock is past C08 (11 Nov 2026), under which a daily review may not open a position at all
    assert out.returncode == 1 and "REJECTED" in out.stderr and "new_positions is not used under C08" in out.stdout


def test_no_janus_trigger_workflows():
    """The quick checks run as two hourly Claude Code scheduled tasks (:15 and :45); no workflow starts Janus."""
    wf = ROOT / ".github/workflows"
    assert not (wf / "janus-weekly.yml").exists() and not (wf / "janus-fire.yml").exists()
    for f in wf.glob("*.yml"):
        assert "JANUS_FIRE" not in f.read_text(), f.name


@pytest.mark.parametrize("over, expect", [
    (dict(market_probability=None), "market_probability is required"),
    (dict(market_probability=0.5), "looks like a fraction"),
    (dict(market_probability=100), "must be in (0, 100)"),
    (dict(market_source=""), "market_source is required"),
    (dict(market_basis="vibes"), "market_basis must be one of"),
    (dict(market_basis="none", market_probability=55), "exactly 50"),
])
def test_market_probability_is_required(tmp_path, over, expect):
    res = J.apply_proposal(review(new_positions=[pos(**over)]), now=NOW, path=tmp_path / "r.jsonl", marks_rows=MARKS)
    assert not res["ok"] and any(expect in e for e in res["errors"]), res["errors"]


def test_market_probability_is_recorded(tmp_path):
    path = tmp_path / "r.jsonl"
    n = pos(market_probability=38, market_basis="prediction market", market_source="Kalshi, Fed December cut, 6 Nov 2026")
    assert J.apply_proposal(review(new_positions=[n]), now=NOW, path=path, marks_rows=MARKS)["ok"]
    o = J.positions(J.load(path))["J001"]["open"]
    assert (o["market_probability"], o["market_basis"]) == (38.0, "prediction market") and "Kalshi" in o["market_source"]


# ----------------------------------------------------------------------------- mandate of 2026-11-09
# the C05 deferral rule alone: the weekend before C06 and C07 (their deferral rules are tested in test_janus_c06.py
# and test_janus_c07.py)
SAT = datetime(2026, 11, 7, 23, 7, tzinfo=timezone.utc)
MON = datetime(2026, 11, 9, 23, 7, tzinfo=timezone.utc)
NO_TRADE = dict(new_positions=[], no_trade_reasoning="Waiting for CPI on the rates ideas.")


def idea(**over):
    d = {"instrument": "US10Y", "direction": "long", "risk_pct": 1.0, "probability": 57, "market_probability": 50,
         "thesis": "Growth is slowing; enter at Monday's mark."}
    d.update(over)
    return d


@pytest.mark.parametrize("sr", [[], None, [{"title": "a note without a link"}], [{"title": "x", "url": "ftp://x"}]])
def test_daily_review_without_research_is_rejected(tmp_path, sr):
    res = J.apply_proposal(review(sources_read=sr), now=NOW, path=tmp_path / "r.jsonl", marks_rows=MARKS)
    assert not res["ok"] and any("sources_read is empty" in e and "counts as failed" in e for e in res["errors"])
    assert [(r["type"], r["status"]) for r in J.load(tmp_path / "r.jsonl")] == [("run", "failed")]   # C06 / Q004


@pytest.mark.parametrize("bb, expect", [
    (None, "below the 3% budget"),
    ({"condition": "no clear edge in rates", "until": "2026-11-18", "reasoning": "x"}, "specific event or condition"),
    ({"condition": "Nothing compelling across the universe", "until": "2026-11-18", "reasoning": "x"}, "specific event"),
    ({"condition": "uncertainty", "until": "2026-11-18", "reasoning": "x"}, "specific event"),
    ({"condition": "US CPI release on 12 Nov decides the Fed call", "until": "2027-01-30", "reasoning": "x"}, "until"),
    ({"condition": "US CPI release on 12 Nov decides the Fed call", "until": "2026-11-18", "reasoning": ""}, "reasoning"),
])
def test_below_three_percent_needs_a_specific_dated_reason(tmp_path, bb, expect):
    res = J.apply_proposal(review(below_budget=bb), now=NOW, path=tmp_path / "r.jsonl", marks_rows=MARKS)
    assert not res["ok"] and any(expect in e for e in res["errors"]), res["errors"]


def test_three_percent_needs_no_reason_and_the_run_records_the_budget(tmp_path):
    path = tmp_path / "r.jsonl"
    three = [pos(instrument="US10Y", stop=5.10), pos(instrument="DE10Y", stop=3.50), pos(instrument="GB10Y", stop=5.40)]
    res = J.apply_proposal(review(new_positions=three, below_budget=None), now=NOW, path=path, marks_rows=MARKS)
    assert res["ok"], res["errors"]
    run = next(r for r in J.load(path) if r["type"] == "run")
    assert run["risk_after_pct"] == 3.0 and run["sources_read"] == SOURCES_READ and "below_budget" not in run
    # a later review below budget records its reason
    res = J.apply_proposal(review(reviews=[{"id": "J001", "action": "close", "reasoning": "CPI trigger fired."},
                                          {"id": "J002", "action": "hold", "reasoning": "On track."},
                                          {"id": "J003", "action": "hold", "reasoning": "On track."}], **NO_TRADE),
                           now=NOW, path=path, marks_rows=MARKS)
    assert res["ok"], res["errors"]
    run = [r for r in J.load(path) if r["type"] == "run"][-1]
    assert run["risk_after_pct"] == 2.0 and run["below_budget"] == BELOW


def test_weekend_review_may_defer_named_ideas(tmp_path):
    path = tmp_path / "r.jsonl"
    ideas = [idea(), idea(instrument="DE10Y", risk_pct=1.0), idea(instrument="EUR", risk_pct=1.0)]
    res = J.apply_proposal(review(below_budget=None, deferred_ideas=ideas, **NO_TRADE), now=SAT, path=path, marks_rows=MARKS)
    assert res["ok"], res["errors"]
    assert [r for r in J.load(path) if r["type"] == "run"][-1]["deferred_ideas"] == ideas
    # still must research
    res = J.apply_proposal(review(below_budget=None, deferred_ideas=ideas, sources_read=[], **NO_TRADE), now=SAT,
                           path=tmp_path / "x.jsonl", marks_rows=MARKS)
    assert not res["ok"] and any("sources_read" in e for e in res["errors"])
    # ideas worth less than the budget still need a reason; a weekday cannot defer
    res = J.apply_proposal(review(below_budget=None, deferred_ideas=ideas[:1], **NO_TRADE), now=SAT,
                           path=tmp_path / "y.jsonl", marks_rows=MARKS)
    assert not res["ok"] and any("below the 3% budget" in e for e in res["errors"])
    res = J.apply_proposal(review(below_budget=None, deferred_ideas=ideas, **NO_TRADE), now=MON,
                           path=tmp_path / "z.jsonl", marks_rows=MARKS)
    assert not res["ok"] and any("weekend and market-holiday reviews only" in e for e in res["errors"])
    res = J.apply_proposal(review(below_budget=None, deferred_ideas=ideas, market_holiday="US Thanksgiving", **NO_TRADE),
                           now=MON, path=tmp_path / "h.jsonl", marks_rows=MARKS)
    assert res["ok"], res["errors"]
    bad = J.apply_proposal(review(below_budget=None, deferred_ideas=[idea(instrument="PLATINUM")], **NO_TRADE),
                           now=SAT, path=tmp_path / "b.jsonl", marks_rows=MARKS)
    assert not bad["ok"] and any("not in the universe" in e for e in bad["errors"])


def test_quick_check_flags_a_failed_or_missing_review_and_low_risk(tmp_path):
    path = tmp_path / "r.jsonl"
    # a pre-mandate review with no sources_read, written directly (the CLI now rejects it)
    J.append(J.load(path), {"type": "run", "session": "daily_review", "date": "2026-11-08", "model": "m",
                            "decided_at": "2026-11-08T23:07:00+00:00", "status": "ok", "n_new": 0, "n_reviews": 0,
                            "sources_read": []}, path)
    t = datetime(2026, 11, 9, 10, 15, tzinfo=timezone.utc)
    rec = J.record_check(["none"], "no change", "claude-opus-5-5", now=t, path=path)
    assert any("failed: empty sources_read" in f and "before the 2026-11-09" in f for f in rec["flags"])
    assert any("below the 3% budget" in f for f in rec["flags"])
    assert "FLAG:" in J.summarize(J.load(path), MARKS, t.date())["last_check"]["result"]
    # a researched review with a current reason clears both flags
    res = J.apply_proposal(review(**NO_TRADE), now=datetime(2026, 11, 9, 23, 7, tzinfo=timezone.utc), path=path,
                           marks_rows=MARKS)
    assert res["ok"], res["errors"]
    rec = J.record_check(["none"], "no change", "claude-opus-5-5", now=datetime(2026, 11, 10, 9, 15, tzinfo=timezone.utc),
                         path=path)
    assert "flags" not in rec
    # two days without a review: missing
    rec = J.record_check(["none"], "no change", "claude-opus-5-5", now=datetime(2026, 11, 12, 9, 15, tzinfo=timezone.utc),
                         path=path)
    assert any("no daily review since 2026-11-09" in f for f in rec["flags"])
    ctx_status = J.review_status(J.load(path), date(2026, 11, 12))
    assert ctx_status["status"] == "missing" and ctx_status["sources_read"] == 2


def test_existing_limits_are_unchanged():
    assert (J.MAX_RISK_POS, J.MAX_RISK_TOTAL, J.MAX_OPEN) == (2.0, 10.0, 8)
    assert J.RISK_BUDGET == (3.0, 10.0) and J.SMALL_EDGE_RISK == (0.25, 0.5) and J.TYPICAL_POSITIONS == (2, 6)
