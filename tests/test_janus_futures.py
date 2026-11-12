"""Janus futures by contract month and defined-risk options (ledger/janus_fut.py): marked from the private
settlement store, records and public files carry P&L in % only."""
import json
from datetime import date, datetime, timezone

import pytest

from ledger import janus as J
from ledger import janus_fut as JF
from ledger import settlements as ST
from test_janus import MARKS, OPP, pos, review

NOW = datetime(2026, 11, 6, 22, 7, tzinfo=timezone.utc)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = tmp_path / "em-macro-data"
    s.mkdir()
    monkeypatch.setenv("EM_MACRO_DATA", str(s))
    return s


def settle(store, prod, month, pts):
    ST.write(store, [{"date": d, "product": prod, "contract_month": month, "settle": f"{v:g}", "source": ST.SOURCE,
                      "source_url": "", "fetched_at": "t", "note": ""} for d, v in pts])


def fut(**over):
    p = pos(instrument="WTI", direction="long", risk_pct=1.0, stop=80.0, horizon="2027-02-15",
            thesis="Supply is tight into winter. Inventories keep drawing.", change_mind="A ceasefire.")
    p.update(over)
    return p


def _open(tmp_path, store, n, pts=(("2026-11-05", 87.0),), prod="WTI", month="2027-01"):
    settle(store, prod, month, pts)
    path = tmp_path / "r.jsonl"
    res = J.apply_proposal(review(new_positions=[n]), now=NOW, path=path, marks_rows=MARKS)
    assert res["ok"], res["errors"]
    return path, J.load(path)


def test_futures_proposal_needs_the_private_store(tmp_path, monkeypatch):
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path / "absent"))
    res = J.apply_proposal(review(new_positions=[fut()]), now=NOW, path=tmp_path / "r.jsonl", marks_rows=MARKS)
    assert not res["ok"] and "em-macro-data" in res["errors"][0]


def test_fill_and_records_never_hold_a_price(tmp_path, store):
    path, recs = _open(tmp_path, store, fut())
    o = J.positions(recs)["J001"]["open"]
    assert o["contract"]["code"] == "CLF27" and "first final exchange settlement" in o["entry_rule"]
    settle(store, "WTI", "2027-01", [("2026-11-09", 88.37), ("2026-11-10", 90.11)])
    J.process(recs, MARKS, date(2026, 11, 10), path)
    p = J.positions(recs)["J001"]
    f = p["fill"]
    assert p["status"] == "open" and f["entry_date"] == "2026-11-09" and f["entry_private"]
    assert f["entry_digest"] == JF.digest("CLF27", "2026-11-09", 88.37)
    for k in ("entry_level", "notional_frac", "notional_usd", "contracts", "one_way_cost"):
        assert k not in f
    text = path.read_text()
    assert "88.37" not in text and "90.11" not in text
    pnl = JF.read_pnl(J.pnl_path(path))
    assert [r["basis"] for r in pnl] == ["entry", "settlement"]
    nf = 0.01 / ((88.37 - 80.0) / 88.37)
    assert float(pnl[-1]["gross_pct"]) == pytest.approx(100 * nf * (90.11 / 88.37 - 1), abs=1e-4)
    assert "90.11" not in J.pnl_path(path).read_text()
    s = J.summarize(recs, MARKS, date(2026, 11, 10), pnl_rows=pnl)
    row = s["positions"][0]
    assert row["mark"] is None and row["mark_history"] == [] and row["net_pnl_pct"] == float(pnl[-1]["net_pct"])
    eq = J.equity(recs, MARKS, date(2026, 11, 10), pnl)
    assert eq[-1][1] == pytest.approx(100 + float(pnl[-1]["net_pct"]))


def test_stop_close_and_costs(tmp_path, store):
    path, recs = _open(tmp_path, store, fut())
    settle(store, "WTI", "2027-01", [("2026-11-09", 88.0), ("2026-11-10", 84.0), ("2026-11-11", 79.5)])
    J.process(recs, MARKS, date(2026, 11, 12), path)
    c = J.positions(recs)["J001"]["close"]
    assert c["reason"] == "stop" and c["date"] == "2026-11-11" and c["outcome"] == "wrong" and c["exit_private"]
    assert c["net_pnl_pct"] < c["gross_pnl_pct"] < -1.0 and "exit_level" not in c
    assert J.verify(recs)["ok"]


def test_roll_keeps_notional_and_captures_roll_yield(tmp_path, store):
    path, recs = _open(tmp_path, store, fut(stop=70.0, horizon="2027-01-30"))
    settle(store, "WTI", "2027-01", [("2026-11-09", 88.0), ("2026-12-10", 90.0)])
    settle(store, "WTI", "2027-02", [("2026-12-10", 89.0), ("2026-12-11", 89.0 * 1.02)])
    J.process(recs, MARKS, date(2026, 12, 11), path)
    p = J.positions(recs)["J001"]
    assert [(r["from_contract"]["code"], r["to_contract"]["code"], r["date"]) for r in p["rolls"]] == \
        [("CLF27", "CLG27", "2026-12-10")]
    last = JF.read_pnl(J.pnl_path(path))[-1]
    nf = 0.01 / ((88.0 - 70.0) / 88.0)
    assert last["contract"] == "CLG27" and float(last["gross_pct"]) == pytest.approx(100 * nf * ((90 / 88 - 1) + 0.02), abs=1e-4)
    assert float(last["costs_pct"]) > p["fill"]["cost_pct"]                  # the roll is charged


def test_capacity_and_universe(tmp_path, store):
    settle(store, "NATGAS", "2027-01", [("2026-11-05", 3.9)])
    res = J.apply_proposal(review(new_positions=[fut(instrument="NATGAS", stop=3.85, risk_pct=2.0)]), now=NOW,
                           path=tmp_path / "r.jsonl", marks_rows=MARKS)
    assert not res["ok"] and any("capacity" in e for e in res["errors"])
    assert {"GOLD", "SILVER", "COPPER", "CORN", "SOYBEANS", "WHEAT", "WTI", "BRENT"} <= set(J.UNIVERSE)
    assert J.UNIVERSE["BRENT"]["proxy"] and J.UNIVERSE["WTI"]["asset_class"] == "future"


def test_tighten_stop_only(tmp_path, store):
    path, recs = _open(tmp_path, store, fut())
    settle(store, "WTI", "2027-01", [("2026-11-09", 88.0)])
    J.process(recs, MARKS, date(2026, 11, 9), path)
    later = datetime(2026, 11, 9, 22, tzinfo=timezone.utc)      # before C06: a one-position book (C06 is tested in test_janus)
    bad = review(new_positions=[], no_trade_reasoning="x",
                 reviews=[{"id": "J001", "action": "tighten_stop", "new_stop": 75.0, "reasoning": "r"}])
    assert "can only be tightened" in J.apply_proposal(bad, now=later, path=path, marks_rows=MARKS)["errors"][0]
    ok = review(new_positions=[], no_trade_reasoning="x",
                reviews=[{"id": "J001", "action": "tighten_stop", "new_stop": 85.0, "reasoning": "r"}])
    assert J.apply_proposal(ok, now=later, path=path, marks_rows=MARKS)["ok"]
    recs = J.load(path)
    settle(store, "WTI", "2027-01", [("2026-11-11", 84.9)])
    J.process(recs, MARKS, date(2026, 11, 11), path)
    assert J.positions(recs)["J001"]["close"]["reason"] == "stop"


GOLD_SPREAD = {"legs": "long 4200 call, short 4600 call", "expiry": "2027-01-26", "iv_pct": 22,
               "iv_source": "estimate"}


def test_option_spread_fill_model_value_and_expiry(tmp_path, store, frozen_repo):
    n = fut(instrument="GOLD", stop=3800.0, horizon="2027-01-26", option=GOLD_SPREAD, contract="2027-02")
    n.pop("direction")
    path, recs = _open(tmp_path, store, n, pts=(("2026-11-05", 4100.0),), prod="GOLD", month="2027-02")
    o = J.positions(recs)["J001"]["open"]
    assert o["option"]["structure"] == "call spread" and o["direction"] == "long"
    settle(store, "GOLD", "2027-02", [("2026-11-09", 4110.0), ("2026-11-10", 4150.0)])
    J.process(recs, MARKS, date(2026, 11, 10), path)
    p = J.positions(recs)["J001"]
    assert p["fill"]["valuation"] == "model estimate" and p["fill"]["premium_private"]
    pnl = JF.read_pnl(J.pnl_path(path))
    assert pnl[-1]["basis"] == "model estimate" and float(pnl[-1]["gross_pct"]) > 0
    # expiry: intrinsic 4500 - 4200 = 300 per oz against the model premium; maximum loss is the % at risk
    settle(store, "GOLD", "2027-02", [("2027-01-26", 4500.0)])
    J.process(recs, MARKS, date(2027, 1, 27), path)
    c = J.positions(recs)["J001"]["close"]
    v0, rpu = JF.option_entry(J.positions(recs)["J001"], ST.read(store), "GOLD")
    assert c["reason"] == "option expiry" and c["basis"] == "intrinsic at expiry"
    assert c["gross_pnl_pct"] == pytest.approx(p["fill"]["risk_pct"] * (300 - v0) / rpu, abs=1e-3)
    assert "4500" not in path.read_text() and "4110" not in path.read_text()


def test_option_worthless_loses_exactly_the_risk(tmp_path, store, frozen_repo):
    n = fut(instrument="GOLD", stop=3000.0, horizon="2027-01-26", option=GOLD_SPREAD, contract="2027-02")
    path, recs = _open(tmp_path, store, n, pts=(("2026-11-05", 4100.0),), prod="GOLD", month="2027-02")
    settle(store, "GOLD", "2027-02", [("2026-11-09", 4100.0), ("2027-01-26", 4000.0)])
    J.process(recs, MARKS, date(2027, 1, 27), path)
    c = J.positions(recs)["J001"]["close"]
    assert c["gross_pnl_pct"] == pytest.approx(-J.positions(recs)["J001"]["fill"]["risk_pct"], abs=1e-6)


@pytest.mark.parametrize("opt, expect", [
    ({**GOLD_SPREAD, "legs": "short 4200 call"}, "naked short"),
    ({**GOLD_SPREAD, "iv_source": ""}, "iv_source"),
    ({**GOLD_SPREAD, "iv_pct": None}, "iv_pct"),
    ({**GOLD_SPREAD, "expiry": "2027-03-26"}, "notice date"),
    ({**GOLD_SPREAD, "legs": "long 4200 call, long 4600 put, short 4800 call"}, "vertical"),
])
def test_option_rule_checks(tmp_path, store, opt, expect, frozen_repo):
    settle(store, "GOLD", "2027-02", [("2026-11-05", 4100.0)])
    n = fut(instrument="GOLD", stop=3800.0, horizon="2027-01-20", option=opt, contract="2027-02")
    res = J.apply_proposal(review(new_positions=[n]), now=NOW, path=tmp_path / "r.jsonl", marks_rows=MARKS)
    assert not res["ok"] and any(expect in e for e in res["errors"]), res["errors"]


def test_horizon_after_expiry_and_credit_spread(tmp_path, store, frozen_repo):
    settle(store, "GOLD", "2027-02", [("2026-11-05", 4100.0)])
    n = fut(instrument="GOLD", stop=3800.0, horizon="2027-02-10", option=GOLD_SPREAD, contract="2027-02")
    res = J.apply_proposal(review(new_positions=[n]), now=NOW, path=tmp_path / "r.jsonl", marks_rows=MARKS)
    assert not res["ok"] and any("after the option expiry" in e for e in res["errors"])
    credit = {**GOLD_SPREAD, "legs": "short 4000 put, long 3800 put"}     # bull put spread: defined risk
    n = fut(instrument="GOLD", stop=3900.0, horizon="2027-01-20", option=credit, contract="2027-02")
    res = J.apply_proposal(review(new_positions=[n]), now=NOW, path=tmp_path / "r2.jsonl", marks_rows=MARKS)
    assert res["ok"], res["errors"]


def test_no_store_leaves_positions_untouched(tmp_path, store, monkeypatch):
    path, recs = _open(tmp_path, store, fut())
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path / "absent"))
    log = J.process(recs, MARKS, date(2026, 11, 10), path)
    assert J.positions(recs)["J001"]["status"] == "pending" and "not processed" in log[0]


def test_futures_needs_feed_the_fetch(tmp_path, store):
    path, recs = _open(tmp_path, store, fut())
    needs = J.futures_needs(recs, date(2026, 11, 6))
    assert needs == {("WTI", "2027-01"): date(2026, 11, 6)}
