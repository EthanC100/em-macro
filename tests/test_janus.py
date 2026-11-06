"""Janus (ledger/janus.py): rules, fills, stops, costs, the hash chain and The Opposition, with no API calls."""
import json
from datetime import date, datetime, timezone

import pytest

from ledger import janus as J
from ledger import pricing as PX


def _m(inst, d, v, unit="% yield", freq="daily", note=""):
    return {"date": d, "instrument": inst, "value": str(v), "unit": unit, "frequency": freq, "source": "test",
            "source_url": "https://example.org", "fetched_at": f"{d}T06:00:00+00:00", "note": note}


MARKS = [_m("US10Y", "2026-11-04", 4.90), _m("US10Y", "2026-11-05", 4.92), _m("WTI", "2026-11-03", 100.0, "USD per bbl"),
         _m("EUR", "2026-11-05", 1.12, "USD per EUR"), _m("JPY", "2026-11-05", 158.0, "JPY per USD")]


def _ask(payload):
    def f(system, prompt):
        assert "Hard rules" in system and "TODAY: 2026-11-06" in prompt
        return {"text": "Here is my answer:\n" + json.dumps(payload), "model": "claude-opus-5-5", "status": "ok",
                "usage": {"input_tokens": 10, "output_tokens": 5}, "searches": 3,
                "sources_read": [{"title": "Fed statement", "url": "https://www.federalreserve.gov/x"}]}
    return f


def _oppose(system, prompt):
    assert "strongest honest case AGAINST" in system
    return {"text": json.dumps({"case_against": "Inflation is sticky.", "key_risks": ["CPI"], "what_proves_it_wrong": "CPI up",
                                "probability_view_wrong": 55, "sources": []}), "model": "claude-opus-5-5", "usage": {}}


NOW = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)


def test_run_opens_positions_with_opposition_and_enforces_rules(tmp_path):
    path = tmp_path / "records.jsonl"
    payload = {"market_summary": "Rates elevated.", "reviews": [],
               "new_positions": [
                   {"instrument": "US10Y", "direction": "long", "risk_pct": 3.5, "stop": 5.10, "horizon": "2026-12-18",
                    "probability": 60, "thesis": "Growth slows. Yields fall.", "change_mind": "Strong payrolls.",
                    "sources": [{"title": "x", "url": "https://x"}]},
                   {"instrument": "GOLD", "direction": "long", "risk_pct": 1, "stop": 1, "horizon": "2026-12-18", "probability": 60},
                   {"instrument": "EUR", "direction": "short", "risk_pct": 1, "stop": 1.10, "horizon": "2026-12-18", "probability": 55,
                    "thesis": "t", "change_mind": "c"},     # stop on the winning side for a short: rejected
               ]}
    res = J.run(now=NOW, ask=_ask(payload), oppose=_oppose, path=path, marks_rows=MARKS)
    recs = J.load(path)
    assert res["ok"] and res["opened"] == ["J001"]
    o = next(r for r in recs if r["type"] == "open")
    assert o["risk_pct"] == 2.0 and o["model"] == "claude-opus-5-5" and o["decision_date"] == "2026-11-06"
    assert o["sources_read"][0]["url"].startswith("https://www.federalreserve.gov")
    assert any("not in the universe" in n for n in res["notes"]) and any("losing side" in n for n in res["notes"])
    opp = next(r for r in recs if r["type"] == "opposition")
    assert opp["position_id"] == "J001" and opp["opposition"]["case_against"] == "Inflation is sticky."
    assert J.verify(recs)["ok"] and recs[0]["type"] == "account_open" and recs[0]["account_usd"] == 500_000_000


def test_no_trade_is_recorded_with_reasoning(tmp_path):
    path = tmp_path / "r.jsonl"
    J.run(now=NOW, ask=_ask({"market_summary": "m", "reviews": [], "new_positions": [], "no_trade_reasoning": "Nothing clears the bar."}),
          oppose=_oppose, path=path, marks_rows=MARKS)
    nt = [r for r in J.load(path) if r["type"] == "no_trade"]
    assert nt and nt[0]["reasoning"] == "Nothing clears the bar."


def test_fill_at_next_mark_stop_close_costs_and_tighten_only(tmp_path):
    path = tmp_path / "r.jsonl"
    payload = {"reviews": [], "new_positions": [{"instrument": "US10Y", "direction": "long", "risk_pct": 1.0, "stop": 5.10,
                                                  "horizon": "2026-12-18", "probability": 60, "thesis": "t", "change_mind": "c"}]}
    J.run(now=NOW, ask=_ask(payload), oppose=_oppose, path=path, marks_rows=MARKS)
    recs = J.load(path)
    marks = MARKS + [_m("US10Y", "2026-11-06", 4.95), _m("US10Y", "2026-11-09", 5.00), _m("US10Y", "2026-11-10", 5.12)]
    # marks dated before the decision date never fill; the 6 Nov mark does
    J.process(recs, MARKS, date(2026, 11, 6), path)
    assert J.positions(recs)["J001"]["status"] == "pending"
    J.process(recs, marks[:-2], date(2026, 11, 7), path)
    p = J.positions(recs)["J001"]
    assert p["status"] == "open" and p["fill"]["entry_level"] == 4.95
    sr = PX.stop_return("yield", "long", 4.95, 5.10)
    assert p["fill"]["notional_frac"] == pytest.approx(0.01 / abs(sr))
    assert p["fill"]["cost_pct"] > 0
    # tighten only: widening is rejected by validate
    rv, _, notes = J.validate({"reviews": [{"id": "J001", "action": "tighten_stop", "new_stop": 5.30}]}, recs, marks, date(2026, 11, 9))
    assert rv[0]["action"] == "hold" and "widen" in notes[0]
    rv, _, _ = J.validate({"reviews": [{"id": "J001", "action": "tighten_stop", "new_stop": 5.05}]}, recs, marks[:-1], date(2026, 11, 9))
    assert rv[0]["action"] == "tighten_stop"
    # the 10 Nov mark (5.12) is through the 5.10 stop: closed as wrong, gross about -1% of the account
    J.process(recs, marks, date(2026, 11, 10), path)
    c = J.positions(recs)["J001"]["close"]
    assert c["reason"] == "stop" and c["outcome"] == "wrong" and c["gross_pnl_pct"] < -1.0 and c["net_pnl_pct"] < c["gross_pnl_pct"]
    s = J.summarize(recs, marks, date(2026, 11, 10))
    assert s["n_closed"] == 1 and s["hit_rate"] == 0.0 and s["brier"] == pytest.approx(0.36)
    assert s["equity"][-1][1] == pytest.approx(100 + c["net_pnl_pct"], abs=1e-6)
    assert J.verify(recs)["ok"]


def test_monthly_or_carried_marks_never_fill_or_stop(tmp_path):
    path = tmp_path / "r.jsonl"
    payload = {"reviews": [], "new_positions": [{"instrument": "US10Y", "direction": "long", "risk_pct": 1.0, "stop": 5.10,
                                                  "horizon": "2026-12-18", "probability": 60, "thesis": "t", "change_mind": "c"}]}
    J.run(now=NOW, ask=_ask(payload), oppose=_oppose, path=path, marks_rows=MARKS)
    recs = J.load(path)
    J.process(recs, MARKS + [_m("US10Y", "2026-11-30", 4.8, freq="monthly"),
                             _m("US10Y", "2026-11-09", 4.9, note="kept previous mark; down")], date(2026, 12, 1), path)
    assert J.positions(recs)["J001"]["status"] == "pending"


def test_hash_chain_detects_an_edit(tmp_path):
    path = tmp_path / "r.jsonl"
    J.run(now=NOW, ask=_ask({"reviews": [], "new_positions": [], "no_trade_reasoning": "x"}), oppose=_oppose, path=path, marks_rows=MARKS)
    recs = J.load(path)
    assert J.verify(recs)["ok"]
    recs[1]["status"] = "edited"
    v = J.verify(recs)
    assert not v["ok"] and "edited" in v["error"]


def test_commodity_roll_rule_and_capacity():
    c = J.front_contract("WTI", date(2026, 11, 6))
    # CLZ26 notice ~20 Nov (inside 35 days), CLF27 ~20 Dec (44 days): F27 is held
    assert c["code"] == "CLF27"
    from ledger import capacity as CAP
    ref = CAP.load_reference()
    reg = J.registry_rows()
    sz = J.size("NATGAS", "long", 2.0, 2.6, 2.0, reg, ref)
    assert sz["capacity_note"] and sz["risk_pct"] < 2.0
    assert sz["capacity"]["pct_adv"] <= CAP.MAX_PCT_ADV + 1e-6
    assert J.calls_needed(0.6) == 153 and J.calls_needed(0.5) is None
