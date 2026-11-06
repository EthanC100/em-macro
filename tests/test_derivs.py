"""Futures by contract month and options in the Me book (ledger/derivs.py): Black-76 pricing, terms and the
Risk Manager, daily marking from the private settlement store (P&L in % only in the public files), closes."""
import csv
import json
import math
import shutil
from datetime import date
from pathlib import Path

import pytest

from conftest import seed_ledger
from ledger import audit, derivs as DV, intake, resolve

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 6)
CALL_SPREAD = [{"q": 1, "kind": "call", "strike": 110.0}, {"q": -1, "kind": "call", "strike": 130.0}]

BLOCK = """DECISION RECORD
Date: 2026-11-06
Country: Oil
Instrument: ICE Brent March 2027 call spread, long $110 call / short $130 call (expiry late Jan 2027)
Action: Buy
Size: 2.0
Probability: 60
Horizon: 2026-12-15
Entry trigger: At market on 6 Nov 2026, March 2027 Brent futures at 94.00; spread premium about 3.00 per barrel.
Stop / exit if wrong: Max loss is the premium paid (2% of account). Exit early if March 2027 Brent futures close below 85.00.
Thesis: Escalation was deferred, not cancelled.
Key factors: Strikes; tanker attacks.
What would change my mind: A signed agreement.
How this differs from market consensus: I put a restart at 60% against about 50% implied.
Premium: 3.00
Underlying at entry: 94.00
Option expiry: 2027-01-26
Implied volatility: implied from premium
"""


# ----------------------------------------------------------------------------- pricing
@pytest.mark.parametrize("F,K,T,s,r", [(94, 110, 0.22, 0.56, 0.04), (94, 80, 1.0, 0.3, 0.05), (2.5, 3.0, 0.1, 0.9, 0.0)])
def test_put_call_parity(F, K, T, s, r):
    c, p = DV.black76("call", F, K, T, s, r), DV.black76("put", F, K, T, s, r)
    assert math.isclose(c - p, math.exp(-r * T) * (F - K), abs_tol=1e-9)


def test_black76_known_value_and_limits():
    # F = K = 100, sigma 20%, T 1, r 0: ATM call = F (2 N(0.1) - 1) = 7.9656
    assert math.isclose(DV.black76("call", 100, 100, 1.0, 0.2), 7.965567, abs_tol=1e-5)
    assert DV.black76("call", 120, 100, 0, 0.5) == 20 and DV.black76("put", 120, 100, 0, 0.5) == 0
    assert DV.black76("put", 80, 100, 0, 0.5) == 20


def test_vertical_spread_bounds():
    T, r = 0.22, 0.04
    prev = -1
    for F in (40, 70, 94, 110, 120, 130, 150, 250):
        for s in (0.1, 0.5, 1.0, 2.0):
            v = DV.structure_value(CALL_SPREAD, F, T, s, r)
            assert -1e-12 <= v <= 20 * math.exp(-r * T) + 1e-9
        v = DV.structure_value(CALL_SPREAD, F, T, 0.5, r)
        assert v >= prev                       # a call spread's value rises with the underlying
        prev = v
    # a credit spread (short the call spread) is bounded by minus the width
    short = [{**l, "q": -l["q"]} for l in CALL_SPREAD]
    assert -20 <= DV.structure_value(short, 120, T, 0.5, r) <= 0


def test_intrinsic_at_expiry():
    t = {"id": "D9", "structure": "call spread", "legs": DV.legs_text(CALL_SPREAD), "option_expiry": "2027-01-26",
         "iv_entry_pct": "56", "iv_source": "x", "entry_date": "2026-11-06", "rate_pct": "4", "entry_premium": "3",
         "risk_per_unit": "3"}
    for F, want in ((100, 0), (118, 8), (125.5, 15.5), (140, 20)):
        v, basis = DV.value(t, F, date(2027, 1, 26), Path("/nonexistent"))
        assert basis == "intrinsic at expiry" and math.isclose(v, want)
        v, basis = DV.value(t, F, date(2027, 2, 3), Path("/nonexistent"))
        assert math.isclose(v, want)
    v, basis = DV.value(t, 118, date(2027, 1, 25), Path("/nonexistent"))
    assert basis == "model estimate" and 0 < v < 20
    # P&L in % of account: size x (value - premium) / premium; max loss is the size
    assert DV.pnl_pct(t, 2.0, 0.0) == -2.0 and DV.pnl_pct(t, 2.0, 8.0) == round(2 * 5 / 3, 4)


def test_implied_vol_roundtrip():
    T, r = 81 / 365, 0.0403
    iv = DV.implied_vol(CALL_SPREAD, 94, T, 3.0, r)
    assert 0.5 < iv < 0.6 and math.isclose(DV.structure_value(CALL_SPREAD, 94, T, iv, r), 3.0, abs_tol=1e-6)
    assert DV.implied_vol(CALL_SPREAD, 94, T, 19.0, r) is None          # above any attainable spread value
    put = [{"q": 1, "kind": "put", "strike": 90.0}]
    iv = DV.implied_vol(put, 94, 0.5, DV.black76("put", 94, 90, 0.5, 0.4, r), r)
    assert math.isclose(iv, 0.4, abs_tol=1e-6)


def test_parsing():
    assert DV.parse_month("ICE Brent March 2027") == "2027-03" and DV.parse_month("BZH27") == "2027-03"
    assert DV.parse_month("Mar 27") == "2027-03" and DV.parse_month("2027-12") == "2027-12"
    assert DV.parse_legs("long $110 call / short $130 call") == CALL_SPREAD
    assert DV.parse_legs("+1 C 110, -1 C 130") == CALL_SPREAD
    assert DV.parse_legs("long put 80") == [{"q": 1, "kind": "put", "strike": 80.0}]
    assert DV.match_product("ICE Brent March 2027 call spread") == "BRENT"
    assert DV.classify(CALL_SPREAD) == "call spread" and DV.classify([]) == "future"


# ----------------------------------------------------------------------------- terms and the Risk Manager
@pytest.fixture()
def ledger_root(tmp_path, monkeypatch):
    root = seed_ledger(tmp_path / "repo")
    store = tmp_path / "em-macro-data"
    store.mkdir()
    monkeypatch.setenv("EM_MACRO_DATA", str(store))
    return root


def _rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_option_decision_terms_and_risk_manager(ledger_root):
    res = intake.process_paste(BLOCK, "clerk", TODAY, ledger_root)
    assert res["ok"], res["comment"]
    rm = res["risk_comment"]
    assert "Risk Manager: passed" in rm and "maximum loss 3 per unit (the premium)" in rm and "(proxy)" in rm
    assert "Stop has a numeric level: 85" in rm and "Implied volatility at entry 56." in rm
    t = DV.load_terms(ledger_root)[res["id"]]
    assert (t["structure"], t["product"], t["contract_month"], t["legs"]) == ("call spread", "BRENT", "2027-03", "+1 call 110|-1 call 130")
    assert t["risk_per_unit"] == "3" and t["iv_source"].startswith("estimate: implied from the stated entry premium")
    assert "data/ledger/derivatives.csv" in res["files"]


@pytest.mark.parametrize("change,err", [
    (("Premium: 3.00", "Premium: 21"), "below its width"),
    (("long $110 call / short $130 call", "short $110 call"), "naked short option"),
    (("Implied volatility: implied from premium", "Implied volatility: 50"), "source"),
    (("Implied volatility: implied from premium\n", ""), "'Implied volatility:' is required"),
    (("Option expiry: 2027-01-26\n", ""), "'Option expiry:'"),
    (("close below 85.00", "close above 99.00"), "winning side"),
])
def test_option_rejections(ledger_root, change, err):
    res = intake.process_paste(BLOCK.replace(*change), "clerk", TODAY, ledger_root)
    assert not res["ok"] and err in res["comment"], res["comment"]
    assert "Risk Manager: rejected" in res["risk_comment"]


def test_option_without_terms_is_not_logged_on_spot(ledger_root):
    body = BLOCK.split("Premium:")[0]
    res = intake.process_paste(body, "clerk", TODAY, ledger_root)
    assert not res["ok"] and "'Premium:'" in res["comment"]


def test_size_rule_still_applies(ledger_root):
    res = intake.process_paste(BLOCK.replace("Size: 2.0", "Size: 2.5"), "clerk", TODAY, ledger_root)
    assert not res["ok"] and "at most 2%" in res["comment"]


# ----------------------------------------------------------------------------- marking
def _settle(store, rows):
    DV.write_settlements(store, [{"date": d, "product": "BRENT", "contract_month": "2027-03", "settle": f"{v:g}",
                                  "source": "CME Group NYMEX Brent Last Day Financial (BZ) settlement",
                                  "source_url": "https://www.cmegroup.com/x", "fetched_at": "t", "note": ""} for d, v in rows])


def test_marking_publishes_pct_only_and_model_value(ledger_root, tmp_path):
    res = intake.process_paste(BLOCK, "clerk", TODAY, ledger_root)
    store = tmp_path / "em-macro-data"
    _settle(store, [("2026-11-06", 94.0), ("2026-11-09", 101.37), ("2026-11-10", 108.0)])
    out = DV.mark(ledger_root, date(2026, 11, 11), fetch=False)
    assert out["closed"] == []
    pnl = _rows(ledger_root / DV.PNL)
    assert list(pnl[0]) == DV.PNL_COLUMNS                     # no price, value or settlement column
    text = (ledger_root / DV.PNL).read_text()
    assert "101.37" not in text and "108" not in text.replace("2026-11-10", "")
    mine = [r for r in pnl if r["id"] == res["id"]]
    assert [r["basis"] for r in mine] == ["entry", "model estimate", "model estimate"]
    t = DV.load_terms(ledger_root)[res["id"]]
    v, _ = DV.value(t, 108.0, date(2026, 11, 10), ledger_root)
    assert float(mine[-1]["pnl_pct"]) == DV.pnl_pct(t, 2.0, v) > float(mine[1]["pnl_pct"]) > 0
    assert (store / "ledger/futures_settlements.csv").exists()
    # the decision is still open, and the spot-proxy resolver leaves it alone (BRENT spot is not its mark)
    dec = next(d for d in _rows(ledger_root / "data/ledger/decisions.csv") if d["id"] == res["id"])
    assert dec["status"] == "open"
    rows = _rows(ledger_root / "data/ledger/decisions.csv")
    changed, _, _ = resolve.process_decisions(rows, [{"date": "2026-12-20", "instrument": "BRENT", "value": "50",
                                                      "frequency": "daily", "unit": "USD per bbl"}],
                                              [{"instrument": "BRENT", "aliases": "ICE Brent|Brent", "book": "janus",
                                                "kind": "commodity", "unit": "USD per bbl", "frequency": "daily"}],
                                              date(2026, 12, 20), ledger_root)
    assert res["id"] not in [d["id"] for d in changed]


def test_stop_closes_at_model_value(ledger_root, tmp_path):
    res = intake.process_paste(BLOCK, "clerk", TODAY, ledger_root)
    _settle(tmp_path / "em-macro-data", [("2026-11-09", 90.0), ("2026-11-10", 84.5), ("2026-11-11", 120.0)])
    out = DV.mark(ledger_root, date(2026, 11, 12), fetch=False)
    assert out["closed"] == [res["id"]]
    d = next(x for x in _rows(ledger_root / "data/ledger/decisions.csv") if x["id"] == res["id"])
    t = DV.load_terms(ledger_root)[res["id"]]
    v, _ = DV.value(t, 84.5, date(2026, 11, 10), ledger_root)
    assert d["status"] == "resolved" and d["outcome"] == "wrong" and float(d["pnl_pct"]) == DV.pnl_pct(t, 2.0, v)
    assert -2.0 <= float(d["pnl_pct"]) < 0 and "stop hit" in d["resolution_note"] and "84.5" not in d["exit_price"]


def test_horizon_and_expiry_closes(ledger_root, tmp_path):
    res = intake.process_paste(BLOCK.replace("Horizon: 2026-12-15", "Horizon: 2027-02-15"), "clerk", TODAY, ledger_root)
    _settle(tmp_path / "em-macro-data", [("2027-01-25", 117.0), ("2027-01-26", 118.0)])
    DV.mark(ledger_root, date(2027, 1, 27), fetch=False)
    d = next(x for x in _rows(ledger_root / "data/ledger/decisions.csv") if x["id"] == res["id"])
    # expiry: intrinsic 118 - 110 = 8 per barrel against a premium of 3: P&L = 2 x 5 / 3
    assert d["status"] == "resolved" and d["outcome"] == "right" and float(d["pnl_pct"]) == round(2 * 5 / 3, 4)
    assert "option expiry" in d["resolution_note"] and "intrinsic at expiry" in d["resolution_note"]


def test_iv_updates_need_a_source(ledger_root):
    res = intake.process_paste(BLOCK, "clerk", TODAY, ledger_root)
    with pytest.raises(ValueError):
        DV.add_iv(res["id"], 60, "estimate", date(2026, 11, 20), ledger_root)
    rec = DV.add_iv(res["id"], 60, "CME CVOL page, 20 Nov 2026", date(2026, 11, 20), ledger_root)
    t = DV.load_terms(ledger_root)[res["id"]]
    assert DV.iv_on(res["id"], date(2026, 11, 19), t, ledger_root)[0] == float(t["iv_entry_pct"])
    assert DV.iv_on(res["id"], date(2026, 11, 21), t, ledger_root) == (60.0, "CME CVOL page, 20 Nov 2026")
    assert rec["id"] == "V001"


def test_resolve_by_hand_uses_the_spread_price(ledger_root):
    res = intake.process_paste(BLOCK, "clerk", TODAY, ledger_root)
    r = intake.process_paste(f"RESOLVE\nId: {res['id']}\nOutcome: right\nExit price or result: 6.00\n", "clerk",
                             date(2026, 12, 1), ledger_root)
    assert r["ok"] and "P&L: **+2.00%**" in r["comment"]        # 2 x (6 - 3) / 3


def test_futures_position_is_linear(ledger_root, tmp_path):
    body = (BLOCK.replace("call spread, long $110 call / short $130 call (expiry late Jan 2027)", "futures")
            .split("Premium:")[0])
    res = intake.process_paste(body, "clerk", TODAY, ledger_root)
    assert res["ok"], res["comment"]
    t = DV.load_terms(ledger_root)[res["id"]]
    assert t["structure"] == "future" and t["risk_per_unit"] == "9"          # |94 - 85|
    _settle(tmp_path / "em-macro-data", [("2026-11-09", 98.5)])
    DV.mark(ledger_root, date(2026, 11, 10), fetch=False)
    last = [r for r in _rows(ledger_root / DV.PNL) if r["id"] == res["id"]][-1]
    assert last["basis"] == "settlement" and float(last["pnl_pct"]) == 1.0      # 2 x 4.5 / 9


def test_terms_are_sealed(ledger_root, monkeypatch):
    intake.process_paste(BLOCK, "clerk", TODAY, ledger_root)
    monkeypatch.setattr(audit, "ROOT", ledger_root)
    seals = ledger_root / "data/ledger/seals.jsonl"
    new = audit.seal(seals)
    assert ("derivative", "entry") in {(s["kind"], s["part"]) for s in new}
    assert audit.verify_seals(seals)["ok"]
