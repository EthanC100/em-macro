"""Config change C08 (approved by Ethan 2026-11-11, docs/config_changes.md): forced forecasts on a fixed watchlist
(janus/watchlist.yaml), every one logged and resolved with Brier scores, and a mechanical book set by the CLI: each
instrument on the side of its final forecast, risk proportional to |p - 50| inside C05's 3-10% band, rebalanced at each
daily review with a 25% no-trade band. The Opposition is advisory. The first C08 review closes J001 and J002. A fund
resolved call is one forecast per instrument per non-overlapping 20-trading-day window.

Every test here fails on the code before C08 (no watchlist, no forecasts, discretionary reviews accepted) and passes
after. The last tests replay the 10 Nov 2026 23:07 UTC review (records 238-241) under C08."""
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from ledger import fund as F
from ledger import janus as J
from ledger import pricing as PX
from test_janus import _m, pos
from test_janus_c06 import LEVELS as LEVELS6, PUBLIC as PUBLIC6, SR, UNITS as UNITS6
from conftest import frozen_copy

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
T = datetime(2026, 11, 11, 23, 7, tzinfo=UTC)                  # Wednesday: the first daily review under C08
WL = ["US10Y", "GB10Y", "DE10Y", "JP10Y", "EUR", "GBP", "JPY", "AUD", "BRL", "MXN"]       # BRL, MXN from C09
P = {"US10Y": 55, "GB10Y": 51, "DE10Y": 48, "JP10Y": 47, "EUR": 52, "GBP": 49, "JPY": 48, "AUD": 52, "BRL": 53,
     "MXN": 48}
EDGES = sum(abs(p - 50) for p in P.values())                  # 23 points -> 2.3% raw, scaled up to the 3% floor
PUBLIC = PUBLIC6 + ("BRL", "MXN")
LEVELS = {**LEVELS6, "BRL": 5.50, "MXN": 18.60}
UNITS = {**UNITS6, "BRL": "BRL per USD", "MXN": "MXN per USD"}


def marks(d="2026-11-09", stale=()):
    """Every public Janus instrument (BRL and MXN included) marked on ``d``; those in ``stale`` on 2026-11-04."""
    return [_m(i, "2026-11-04" if i in stale else d, LEVELS[i], UNITS.get(i, "% yield")) for i in PUBLIC]
OPP = {"case_against": "The move is priced and positioning is crowded the other way.", "probability_view_wrong": 55,
       "model": "claude-opus-5-5"}


@pytest.fixture(autouse=True)
def no_store(tmp_path, monkeypatch):
    """No private settlements (the watchlist has no futures; a test never clones em-macro-data)."""
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path / "no-store"))


def fc(inst, p=None, p0=None, **over):
    p = P[inst] if p is None else p
    return {"instrument": inst, "p_initial": p if p0 is None else p0, "p_final": p,
            "reasoning": "Positioning and the latest data lean this way over the next month.", "opposition": OPP,
            **over}


def c08(now=T, probs=None, **over):
    probs = {**P, **(probs or {})}
    return {"session": "daily_review", "model": "claude-opus-5-5", "market_summary": "Yields drifted lower.",
            "sources_read": SR, "time_anchor": {"now_utc": now.isoformat(), "events": []},
            "forecasts": [fc(i, probs[i]) for i in WL], **over}


def run(tmp_path, ans, now=T, mk=None, name="r.jsonl", dry_run=False):
    return J.apply_proposal(ans, now=now, path=tmp_path / name, marks_rows=marks("2026-11-10") if mk is None else mk,
                            dry_run=dry_run)


def errs_with(res, text):
    return [e for e in res["errors"] if text in e]


def day_marks(d, move=0.0):
    """Every public instrument marked on ``d``, each moved by ``move`` (yields in points, FX in %)."""
    out = []
    for i in PUBLIC:
        v = LEVELS[i] + move if UNITS.get(i, "% yield") == "% yield" else LEVELS[i] * (1 + move / 100)
        out.append(_m(i, d if isinstance(d, str) else d.isoformat(), round(v, 6), UNITS.get(i, "% yield")))
    return out


def weekdays(a: date, b: date):
    d = a
    while d <= b:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def book(path):
    return {p["open"]["instrument"]: p for p in J.positions(J.load(path)).values()
            if p["status"] in ("open", "pending") and p["open"].get("c08")}


# ----------------------------------------------------------------------------- 1. the watchlist
def test_the_watchlist_has_liquid_instruments_janus_already_marks_daily():
    wl = J.load_watchlist()
    names = [w["instrument"] for w in wl]
    assert names == WL and 6 <= len(wl) <= 11 and {"US10Y", "GB10Y", "BRL", "MXN"} <= set(names)   # C09: 11 at most
    reg = J.registry_rows()
    for w in wl:
        assert w["instrument"] in J.UNIVERSE and not J.is_future(w["instrument"])      # public marks only (rule 7)
        assert reg[w["instrument"]]["frequency"] == "daily"
        assert w["horizon_trading_days"] == 20 and "20 trading days" in w["question"]
        assert w["yes_if"] in ("lower", "higher") and w["yes_position"] == "long"
        assert f"registry row {w['instrument']}" in w["resolution_source"]          # resolved on Janus's own mark
        assert w["stop"]["unit"] in ("yield_points", "percent") and w["stop"]["distance"] > 0
        # YES is the long side: a move in the yes_if direction is a gain for a long position
        k, v = J.kind(w["instrument"], reg), LEVELS[w["instrument"]]
        moved = v * (0.99 if w["yes_if"] == "lower" else 1.01)
        assert PX.position_return(k, "long", v, moved) > 0


def test_the_resolution_rule_counts_20_weekdays_from_the_base_mark():
    assert J.add_weekdays(date(2026, 11, 11), 20) == date(2026, 12, 9)
    assert J.add_weekdays(date(2026, 11, 13), 1) == date(2026, 11, 16)                # Friday -> Monday


# ----------------------------------------------------------------------------- 2. forecasts
def test_a_c08_review_logs_every_forecast_and_the_cli_sets_the_book(tmp_path):
    res = run(tmp_path, c08())
    assert res["ok"], res["errors"]
    recs = J.load(tmp_path / "r.jsonl")
    run_rec = next(r for r in recs if r["type"] == "run")
    assert run_rec["c08"] and run_rec["n_forecasts"] == 10 and run_rec["risk_after_pct"] == pytest.approx(3.0)
    fcs = [r for r in recs if r["type"] == "forecast"]
    assert [f["instrument"] for f in fcs] == WL and [f["forecast_id"] for f in fcs][:2] == ["JF0001", "JF0002"]
    assert all(f["p_initial"] == f["p_final"] == P[f["instrument"]] for f in fcs)
    assert all(f["horizon_trading_days"] == 20 and f["resolution_source"] and f["question"] for f in fcs)
    assert fcs[0]["market_probability"] == 50.0 and fcs[0]["market_basis"] == "none"       # C04 default
    b = book(tmp_path / "r.jsonl")
    assert {i: p["open"]["direction"] for i, p in b.items()} == {
        i: ("long" if P[i] > 50 else "short") for i in WL}
    # risk proportional to |p - 50| (23 points -> 2.3%, scaled up to the 3% floor)
    for i, p in b.items():
        assert p["open"]["risk_pct"] == pytest.approx(3.0 * abs(P[i] - 50) / EDGES, abs=1e-6)
        assert p["open"]["forecast_id"] and p["open"]["set_by"] == "CLI (C08)" and p["open"]["c08"]
    assert sum(p["open"]["risk_pct"] for p in b.values()) == pytest.approx(3.0, abs=1e-5)
    assert J.verify(recs)["ok"]


def no_aud(f):
    return [x for x in f if x["instrument"] != "AUD"]


@pytest.mark.parametrize("change, expect", [
    (lambda f: no_aud(f), "missing AUD"),
    (lambda f: f + [fc("EUR")], "forecast 11 (EUR): forecast twice"),
    (lambda f: no_aud(f) + [{**fc("AUD"), "instrument": "CHF"}], "forecast 10 (CHF): not on the watchlist"),
    (lambda f: no_aud(f) + [fc("AUD", 50)], "p_final is 50, which is not a forecast"),
    (lambda f: no_aud(f) + [fc("AUD", 52, p0=50)], "p_initial is 50, which is not a forecast"),
    (lambda f: no_aud(f) + [fc("AUD", 100)], "p_final must be a whole number from 1 to 99"),
    (lambda f: no_aud(f) + [fc("AUD", 0)], "p_final must be a whole number from 1 to 99"),
    (lambda f: no_aud(f) + [fc("AUD", 55.5)], "p_final must be a whole number from 1 to 99"),
    (lambda f: no_aud(f) + [{**fc("AUD"), "p_initial": None}], "p_initial must be a whole number"),
    (lambda f: no_aud(f) + [fc("AUD", reasoning="")], "forecast 10 (AUD): reasoning is required"),
    (lambda f: no_aud(f) + [fc("AUD", opposition={})], "opposition.case_against is required"),
    (lambda f: no_aud(f) + [fc("AUD", market_probability=0.5, market_basis="options", market_source="x")],
     "looks like a fraction"),
    (lambda f: [], "forecasts (C08): required"),
])
def test_every_review_forecasts_every_watchlist_instrument_between_1_and_99_never_50(tmp_path, change, expect):
    ans = c08()
    ans["forecasts"] = change(ans["forecasts"])
    res = run(tmp_path, ans)
    assert not res["ok"] and errs_with(res, expect), res["errors"]


def test_a_forecast_may_give_a_market_implied_probability(tmp_path):
    ans = c08()
    ans["forecasts"][0] = fc("US10Y", market_probability=47, market_basis="options",
                             market_source="10y Treasury options, 20-day risk-neutral probability")
    assert run(tmp_path, ans)["ok"]
    f = next(r for r in J.load(tmp_path / "r.jsonl") if r["type"] == "forecast")
    assert (f["market_probability"], f["market_basis"]) == (47.0, "options")


# ----------------------------------------------------------------------------- 3. the CLI sets the book
@pytest.mark.parametrize("field, value", [
    ("new_positions", [pos(instrument="US10Y", stop=5.10, risk_pct=0.5)]),
    ("reviews", [{"id": "J001", "action": "hold", "reasoning": "on track"}]),
    ("below_budget", {"condition": "FOMC on 9 Dec decides the hike", "type": "event", "event_date": "2026-12-09",
                      "calendar_url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                      "until": "2026-12-10", "reasoning": "hold less until then"}),
    ("candidates", [{"instrument": "EUR", "direction": "long", "probability": 55}]),
    ("deferred_ideas", [{"instrument": "EUR", "direction": "long", "risk_pct": 0.5, "probability": 55}]),
])
def test_discretionary_fields_are_rejected(tmp_path, field, value):
    res = run(tmp_path, c08(**{field: value}))
    assert not res["ok"] and errs_with(res, f"{field} is not used under C08"), res["errors"]


def test_targets_are_proportional_to_the_edge_and_scaled_into_the_3_to_10_band():
    t = J.c08_targets({"US10Y": 60, "EUR": 45, "JPY": 58})                  # 1.0 + 0.5 + 0.8 = 2.3% -> 3%
    assert sum(x["risk_pct"] for x in t.values()) == pytest.approx(3.0)
    assert t["US10Y"]["risk_pct"] / t["EUR"]["risk_pct"] == pytest.approx(2.0)
    assert (t["US10Y"]["direction"], t["EUR"]["direction"]) == ("long", "short")
    inside = J.c08_targets({"US10Y": 70, "GB10Y": 30, "EUR": 60, "JPY": 35})  # 2 + 2 + 1 + 1.5 = 6.5%: unscaled
    assert [inside[i]["risk_pct"] for i in ("US10Y", "GB10Y", "EUR", "JPY")] == [2.0, 2.0, 1.0, 1.5]
    big = J.c08_targets({i: 80 for i in WL})                                # 8 x 2% = 16% -> 10%
    assert sum(x["risk_pct"] for x in big.values()) == pytest.approx(10.0)
    capped = J.c08_targets({"US10Y": 99, "EUR": 51, "JPY": 51})             # 2 (cap) + 0.1 + 0.1 -> 3%: the rest
    assert capped["US10Y"]["risk_pct"] == 2.0 and capped["EUR"]["risk_pct"] == pytest.approx(0.5)
    assert set(J.c08_targets({"US10Y": 60, "EUR": 45}, excluded={"EUR"})) == {"US10Y"}


def test_daily_rebalance_holds_inside_the_25_percent_band_resizes_outside_it_and_flips_sides(tmp_path):
    path = tmp_path / "r.jsonl"
    assert run(tmp_path, c08())["ok"]
    recs = J.load(path)
    J.process(recs, marks("2026-11-10") + day_marks("2026-11-11"), date(2026, 11, 12), path)
    assert all(p["status"] == "pending" for p in book(path).values())          # C11: not at the review day's mark
    J.process(J.load(path), day_marks("2026-11-11") + day_marks("2026-11-12"), date(2026, 11, 13), path)
    first = book(path)
    assert all(p["status"] == "open" for p in first.values())
    t2 = T + timedelta(days=1)
    # edges 6, 4, 2, 8, 2, 1, 2, 2, 3, 2 = 3.2%, inside the band: US10Y 55 -> 56 (0.60% vs 0.65% held: -8%, inside
    # the no-trade band), GB10Y 51 -> 46 (flip), JP10Y 47 -> 42 (0.80% vs 0.39%: resized)
    probs = {"US10Y": 56, "GB10Y": 46, "JP10Y": 42}
    dry = run(tmp_path, c08(now=t2, probs=probs), now=t2, mk=marks("2026-11-12"), dry_run=True)
    assert dry["ok"] and first["US10Y"]["id"] in dry["would_hold"], dry
    assert {first["GB10Y"]["id"], first["JP10Y"]["id"]} <= set(dry["would_close"])
    assert run(tmp_path, c08(now=t2, probs=probs), now=t2, mk=marks("2026-11-12"))["ok"]
    after = book(path)
    assert after["US10Y"]["id"] == first["US10Y"]["id"]                          # held
    assert after["GB10Y"]["open"]["direction"] == "short" and after["GB10Y"]["open"]["flips"] == first["GB10Y"]["id"]
    assert after["JP10Y"]["open"]["replaces"] == first["JP10Y"]["id"]
    total = sum(p["open"]["risk_pct"] if p["status"] == "pending" else J._held_risk(p) for p in after.values())
    assert 3.0 - 1e-6 <= total <= 10.0


def test_a_resize_fills_at_one_mark_and_pays_costs_only_on_the_notional_traded(tmp_path):
    path = tmp_path / "r.jsonl"
    run(tmp_path, c08())
    J.process(J.load(path), day_marks("2026-11-12"), date(2026, 11, 13), path)
    old = book(path)["JP10Y"]
    t2 = T + timedelta(days=1)
    assert run(tmp_path, c08(now=t2, probs={"JP10Y": 40, "GB10Y": 45}), now=t2, mk=day_marks("2026-11-12"))["ok"]
    J.process(J.load(path), day_marks("2026-11-12") + day_marks("2026-11-13", 0.01), date(2026, 11, 14), path)
    pos_ = J.positions(J.load(path))
    new = book(path)["JP10Y"]
    close = pos_[old["id"]]["close"]
    assert close["reason"] == "C08 rebalance" and close["date"] == new["fill"]["entry_date"] == "2026-11-13"
    carried = min(old["fill"]["notional_frac"], new["fill"]["notional_frac"])
    assert close["carried_notional_frac"] == pytest.approx(carried) and new["fill"]["carried_from"] == old["id"]
    traded = new["fill"]["notional_frac"] - carried
    assert new["fill"]["cost_pct"] == pytest.approx(100 * traded * (new["fill"]["one_way_cost"]
                                                                    + new["fill"]["impact_frac"]), abs=1e-5)
    assert close["exit_cost_pct"] == pytest.approx(0.0, abs=1e-9)                # it grew: nothing was sold
    # a side flip pays in full on both legs
    gb_old = [p for p in pos_.values() if p["open"]["instrument"] == "GB10Y" and p["close"]][0]
    assert gb_old["close"]["reason"] == "C08 side flip" and gb_old["close"]["carried_notional_frac"] == 0.0
    assert gb_old["close"]["exit_cost_pct"] > 0
    assert J.verify(J.load(path))["ok"]


def test_a_resize_is_not_a_closed_call_awaiting_a_post_mortem(tmp_path, monkeypatch):
    """Like the algorithm's resizes, a C08 resize continues the same view: no post-mortem is due for it, while a
    side flip is a real close and gets one."""
    from ledger import postmortem as PM
    path = tmp_path / "r.jsonl"
    run(tmp_path, c08())
    J.process(J.load(path), day_marks("2026-11-12"), date(2026, 11, 13), path)
    t2 = T + timedelta(days=1)
    run(tmp_path, c08(now=t2, probs={"JP10Y": 40, "GB10Y": 45}), now=t2, mk=day_marks("2026-11-12"))
    J.process(J.load(path), day_marks("2026-11-12") + day_marks("2026-11-13", 0.01), date(2026, 11, 14), path)
    load = J.load
    monkeypatch.setattr(PM.JN, "load", lambda p=path: load(p))
    monkeypatch.setattr(PM, "_rows", lambda f: [])
    monkeypatch.setattr(PM, "POS_FILES", {})
    reasons = {c["record"]["instrument"]: c["record"]["reason"] for c in PM.candidates(day_marks("2026-11-13"))
               if c["book"] == "janus"}
    assert reasons.get("GB10Y") == "C08 side flip" and "JP10Y" not in reasons, reasons


def test_only_a_named_data_failure_excludes_an_instrument_and_it_is_still_forecast(tmp_path):
    stale = [m for m in marks("2026-11-10") if m["instrument"] != "GB10Y"] + [_m("GB10Y", "2026-11-04", 5.2)]
    # without naming it, the stale instrument stays in the book
    res = run(tmp_path, c08(), mk=stale, dry_run=True)
    assert res["ok"] and "GB10Y" in [o[0] for o in res["would_open"]]
    df = [{"instrument": "GB10Y", "mark": "BoE IUDMNPY daily gilt yield", "last_mark": "2026-11-04"}]
    res = run(tmp_path, c08(data_failure=df), mk=stale)
    assert res["ok"], res["errors"]
    recs = J.load(tmp_path / "r.jsonl")
    assert "GB10Y" not in book(tmp_path / "r.jsonl")
    assert next(r for r in recs if r["type"] == "forecast" and r["instrument"] == "GB10Y")["excluded"] is True
    assert sum(p["open"]["risk_pct"] for p in book(tmp_path / "r.jsonl").values()) == pytest.approx(3.0, abs=1e-5)


@pytest.mark.parametrize("df, mk_stale, expect", [
    ([{"instrument": "GB10Y", "mark": "BoE gilt yield", "last_mark": "2026-11-10"}], False, "is current"),
    ([{"instrument": "GB10Y", "mark": "BoE gilt yield", "last_mark": "2026-11-03"}], True, "does not match"),
    ([{"instrument": "CHF", "mark": "ECB CHF reference rate", "last_mark": "none"}], False, "not on the watchlist"),
    ([{"instrument": "GB10Y", "last_mark": "2026-11-04"}], True, "mark is required"),
])
def test_a_data_failure_must_be_real(tmp_path, df, mk_stale, expect):
    mk = marks("2026-11-10", stale=("GB10Y",)) if mk_stale else marks("2026-11-10")
    res = run(tmp_path, c08(data_failure=df), mk=mk)
    assert not res["ok"] and errs_with(res, expect) and len(res["errors"]) == 1, res["errors"]


def test_an_instrument_without_any_mark_must_be_named(tmp_path):
    mk = [m for m in marks("2026-11-10") if m["instrument"] != "JP10Y"]
    res = run(tmp_path, c08(), mk=mk)
    assert not res["ok"] and errs_with(res, "JP10Y has no mark"), res["errors"]
    df = [{"instrument": "JP10Y", "mark": "MoF JGB curve CSV", "last_mark": "none"}]
    assert run(tmp_path, c08(data_failure=df), mk=mk)["ok"]


# ----------------------------------------------------------------------------- 4. The Opposition is advisory
def test_the_opposition_never_vetoes_a_forecast(tmp_path):
    ans = c08()
    ans["forecasts"][0] = fc("US10Y", 62, p0=58, opposition={"case_against": "This is plainly wrong: hikes are coming.",
                                                             "probability_view_wrong": 95})
    ans["forecasts"][4] = fc("EUR", 55, p0=45)             # The Opposition flipped it the other way: still logged
    res = run(tmp_path, ans)
    assert res["ok"], res["errors"]
    recs = J.load(tmp_path / "r.jsonl")
    us = next(r for r in recs if r["type"] == "forecast" and r["instrument"] == "US10Y")
    assert (us["p_initial"], us["p_final"], us["opposition"]["probability_view_wrong"]) == (58, 62, 95)
    assert book(tmp_path / "r.jsonl")["US10Y"]["open"]["direction"] == "long"


# ----------------------------------------------------------------------------- 5. J001 and J002
def _chain_until(seq):
    return [json.loads(x) for x in frozen_copy("data/janus/records.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip() and json.loads(x)["seq"] <= seq]


def _write(path, recs):
    path.write_text("".join(json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
                            for r in recs))


def test_the_first_c08_review_closes_j001_and_j002_without_editing_any_record(tmp_path):
    recs = _chain_until(245)                                  # the chain as C08 was recorded (11 Nov, 00:48 UTC)
    assert J.verify(recs)["ok"]
    path = tmp_path / "r.jsonl"
    _write(path, recs)
    before = path.read_text()
    # ledger-daily fills both at the 10 Nov marks before the review
    mk = marks("2026-11-10")
    J.process(J.load(path), mk, date(2026, 11, 11), path)
    st = J.positions(J.load(path))
    assert st["J001"]["status"] == st["J002"]["status"] == "open"
    res = J.apply_proposal(c08(), now=T, path=path, marks_rows=mk)
    assert res["ok"], res["errors"]
    assert path.read_text().startswith(before)                # append-only: records 1-245 unchanged
    new = J.load(path)[245:]
    for pid in ("J001", "J002"):
        rv = next(r for r in new if r["type"] == "review" and r["position_id"] == pid)
        cr = next(r for r in new if r["type"] == "close_request" and r["position_id"] == pid)
        assert rv["action"] == "close" and cr["close_reason"] == "C08 rule 5: discretionary position closed"
    assert res["opened"] == [f"J{n:03d}" for n in range(3, 13)]
    J.process(J.load(path), mk + day_marks("2026-11-11"), date(2026, 11, 12), path)
    st = J.positions(J.load(path))
    assert st["J001"]["status"] == "open"                      # C11: not closed at the review day's own mark
    J.process(J.load(path), mk + day_marks("2026-11-11") + day_marks("2026-11-12"), date(2026, 11, 13), path)
    st = J.positions(J.load(path))
    assert st["J001"]["close"]["date"] == "2026-11-12"
    for pid in ("J001", "J002"):
        assert st[pid]["status"] == "closed" and st[pid]["close"]["reason"] == "C08 rule 5: discretionary position closed"
    assert J.verify(J.load(path))["ok"]


def test_a_quick_check_cannot_close_or_tighten_a_c08_position(tmp_path):
    path = tmp_path / "r.jsonl"
    run(tmp_path, c08())
    pid = book(path)["US10Y"]["id"]
    qc = {"session": "quick_check", "model": "m", "reviews": [{"id": pid, "action": "close", "reasoning": "trigger"}]}
    res = J.apply_proposal(qc, now=T + timedelta(hours=1), path=path, marks_rows=marks("2026-11-10"))
    assert not res["ok"] and errs_with(res, "a C08 position is set by the CLI"), res["errors"]


# ----------------------------------------------------------------------------- forecasts resolve, Brier scored
def test_every_forecast_resolves_after_20_trading_days_with_brier_scores(tmp_path):
    path = tmp_path / "r.jsonl"
    df = [{"instrument": "GB10Y", "mark": "BoE IUDMNPY daily gilt yield", "last_mark": "2026-11-04"}]
    stale = marks("2026-11-10", stale=("GB10Y",))
    assert run(tmp_path, c08(data_failure=df), mk=stale)["ok"]            # GB10Y: no position, still forecast
    mk = []
    for d in weekdays(date(2026, 11, 11), date(2026, 12, 11)):
        mk += day_marks(d, -0.05 if d >= date(2026, 12, 1) else 0.0)        # yields down 5bp, FX down 0.05%
    mk = [m for m in mk if not (m["instrument"] == "EUR" and m["date"] >= "2026-12-01")] + \
        [_m("EUR", d.isoformat(), LEVELS["EUR"], "USD per EUR") for d in weekdays(date(2026, 12, 1), date(2026, 12, 11))]
    J.process(J.load(path), mk, date(2026, 12, 9), path)                   # before the end mark: nothing resolves
    assert not [r for r in J.load(path) if r["type"] == "forecast_resolution"]
    J.process(J.load(path), mk, date(2026, 12, 10), path)
    res = {r["instrument"]: r for r in J.load(path) if r["type"] == "forecast_resolution"}
    assert set(res) == set(WL)                                              # GB10Y too, though it had no position
    us = res["US10Y"]
    # C11: the base mark is the first dated after the review's UTC date (11 Nov), not that day's own close
    assert (us["base_date"], us["target_date"], us["end_date"]) == ("2026-11-12", "2026-12-10", "2026-12-10")
    assert us["answer"] == "YES" and us["brier_final"] == pytest.approx((0.55 - 1) ** 2)
    assert us["brier_market"] == pytest.approx(0.25)
    assert res["EUR"]["answer"] == "NO"                                     # unchanged mark: NO
    assert res["JPY"]["answer"] == "YES" and res["AUD"]["answer"] == "YES"  # yen and AUD per USD lower: stronger
    assert res["GBP"]["answer"] == "NO"                                     # USD per GBP lower: GBP/USD not higher
    s = J.summarize(J.load(path), mk, date(2026, 12, 10))["forecast_summary"]
    assert s["n_resolved"] == 10 and s["brier_final"] == pytest.approx(
        sum(r["brier_final"] for r in res.values()) / 10, abs=1e-4)
    assert res["BRL"]["answer"] == "YES" and res["MXN"]["answer"] == "YES"  # reais and pesos per USD lower
    J.process(J.load(path), mk, date(2026, 12, 11), path)                   # resolved once
    assert len([r for r in J.load(path) if r["type"] == "forecast_resolution"]) == 10


# ----------------------------------------------------------------------------- 6. fund resolved calls
def _forecast(recs, path, inst, d, p, base, end, outcome, **extra):
    n = sum(1 for r in recs if r["type"] == "forecast") + 1
    fid = f"JF{n:04d}"
    J.append(recs, {"type": "forecast", "forecast_id": fid, "instrument": inst, "date": d, "p_initial": p,
                    "p_final": p, "market_probability": 50.0, "yes_if": "lower", **extra}, path)
    if end:
        J.append(recs, {"type": "forecast_resolution", "forecast_id": fid, "instrument": inst, "base_date": base,
                        "end_date": end, "outcome": outcome, "answer": "YES" if outcome else "NO",
                        "brier_final": (p / 100 - outcome) ** 2, "brier_initial": (p / 100 - outcome) ** 2,
                        "brier_market": 0.25}, path)
    return fid


def _daily_forecasts(path, insts, last_resolved=date(2027, 1, 8), n_days=45, shift=None):
    """One forecast a weekday on each of ``insts`` from 11 Nov 2026 (base = forecast date, or ``shift[inst]``
    weekdays later), resolved 20 weekdays after its base when that falls on or before ``last_resolved``."""
    recs, ids = [], {}
    for d in list(weekdays(date(2026, 11, 11), date(2027, 2, 26)))[:n_days]:
        for inst in insts:
            base = J.add_weekdays(d, (shift or {}).get(inst, 0))
            end = J.add_weekdays(base, 20)
            ids[(inst, d)] = _forecast(recs, path, inst, d.isoformat(), 60 if inst != "GB10Y" else 45,
                                       base.isoformat(), end.isoformat() if end <= last_resolved else None, 1)
    return recs, ids


def test_a_fund_call_is_one_per_correlation_cluster_per_non_overlapping_window(tmp_path):
    """C09: forecasts on US10Y and GB10Y (both G10 yields) made in one review are one call, scored on their mean
    Brier; EUR (USD vs G10 FX) is its own cluster. Daily forecasts over 45 weekdays give 2 windows per cluster: 4
    calls, where counting per instrument would give 6."""
    recs, ids = _daily_forecasts(tmp_path / "r.jsonl", ("US10Y", "GB10Y", "EUR"))
    calls = J.fund_calls(recs)
    assert [(c["cluster"], c["date"]) for c in calls] == [
        ("g10_yields", "2026-11-11"), ("usd_g10_fx", "2026-11-11"), ("g10_yields", "2026-12-09"),
        ("usd_g10_fx", "2026-12-09")]
    first = calls[0]
    assert first["instruments"] == ["US10Y", "GB10Y"]
    assert first["forecast_ids"] == [ids[("US10Y", date(2026, 11, 11))], ids[("GB10Y", date(2026, 11, 11))]]
    assert first["brier_final"] == pytest.approx(((0.6 - 1) ** 2 + (0.45 - 1) ** 2) / 2)    # mean over the cluster
    assert calls[2]["base_date"] == first["end_date"]                       # windows abut, never overlap
    assert J.forecast_summary(recs)["fund_calls"] == 4
    assert {c for c, ms in J.load_clusters().items() if ms} == {"g10_yields", "usd_g10_fx", "em_fx"}


def test_a_cluster_window_spans_all_its_forecasts_and_waits_for_all_of_them(tmp_path):
    # GB10Y's base mark comes a weekday later (a UK holiday, say): the call's window ends at GB10Y's end mark, so the
    # next counted call starts on or after it
    recs, _ = _daily_forecasts(tmp_path / "r.jsonl", ("US10Y", "GB10Y"), shift={"GB10Y": 1})
    calls = [c for c in J.fund_calls(recs) if c["cluster"] == "g10_yields"]
    assert (calls[0]["base_date"], calls[0]["end_date"]) == ("2026-11-11", "2026-12-10")
    assert calls[1]["date"] == "2026-12-10" and calls[1]["base_date"] >= calls[0]["end_date"]
    # a call resolves only when every forecast in it has: one open member holds the cluster's chain
    recs, _ = _daily_forecasts(tmp_path / "b.jsonl", ("US10Y",), n_days=1)
    _forecast(recs, tmp_path / "b.jsonl", "GB10Y", "2026-11-11", 45, None, None, 0)
    assert J.fund_calls(recs) == []


def test_a_forecast_keeps_the_cluster_recorded_with_it(tmp_path):
    path = tmp_path / "r.jsonl"
    assert run(tmp_path, c08())["ok"]
    fcs = {r["instrument"]: r["cluster"] for r in J.load(path) if r["type"] == "forecast"}
    assert fcs == {**{i: "g10_yields" for i in ("US10Y", "GB10Y", "DE10Y", "JP10Y")},
                   **{i: "usd_g10_fx" for i in ("EUR", "GBP", "JPY", "AUD")}, "BRL": "em_fx", "MXN": "em_fx"}
    recs, _ = _daily_forecasts(tmp_path / "x.jsonl", ("EUR",), n_days=1)
    recs[0]["cluster"] = "em_fx"                      # what was recorded counts, not today's file
    assert J.fund_calls(recs)[0]["cluster"] == "em_fx"


def test_the_fund_counts_c08_calls_and_janus_pnl_from_10_november(tmp_path):
    calls = [{"end_date": "2026-12-%02d" % (1 + i % 28), "brier_final": 0.16, "brier_market": 0.25}
             for i in range(30)]
    series = [["2026-11-06", 100.0], ["2026-11-10", 99.8], ["2026-12-31", 100.6]]
    s = F.janus_share([], series, date(2026, 12, 31), calls)
    assert s["resolved_calls"] == 30 and s["net_pnl_pct_on_those_calls"] == pytest.approx(0.8)
    assert s["brier_janus"] == pytest.approx(0.16) and s["brier_market"] == pytest.approx(0.25)
    assert s["share"] == F.JANUS_UP
    assert F.janus_share([], series, date(2026, 12, 31), calls[:29])["share"] == F.JANUS_START
    losing = [["2026-11-10", 100.0], ["2026-12-31", 99.5]]
    assert F.janus_share([], losing, date(2026, 12, 31), calls)["share"] == F.JANUS_LOW
    # closed positions do not count as calls under C08 (J001/J002's closes are not resolved calls)
    closed = [{"probability": 60, "market_probability": 50, "close": {"date": "2026-11-12", "outcome": "right",
                                                                       "net_pnl_pct": 1.0}}] * 40
    assert F.janus_share(closed, series, date(2026, 12, 31), [])["resolved_calls"] == 0


def test_the_fund_reads_janus_calls_from_its_summary():
    books = {"algorithm": {"versions": [{"id": "v1.1", "series": [], "live_start": None}]},
             "janus": {"series": [], "live_start": None, "summary": {"closed": [], "fund_calls": []}},
             "me": {"series": [], "live_start": None}}
    f = F.build_fund(books, date(2026, 11, 20))
    assert f["allocation"]["janus_rule"]["definition"].startswith("C09: one call per correlation cluster")


# ----------------------------------------------------------------------------- 7. kept rules
def test_kept_failed_review_records_and_futures_details_withheld(tmp_path):
    ans = c08()
    ans["forecasts"][-1] = {**fc("AUD"), "instrument": "WTI"}
    res = run(tmp_path, ans)
    assert not res["ok"] and res["failed_record"] == 1
    rec = J.load(tmp_path / "r.jsonl")[0]
    assert (rec["type"], rec["status"], rec["c08"]) == ("run", "failed", True)
    wti = [e for e in rec["errors"] if "WTI" in e]
    assert wti and all("details not recorded" in e for e in wti)
    assert J.review_status(J.load(tmp_path / "r.jsonl"), date(2026, 11, 11))["status"] == "failed"


def test_kept_research_and_the_time_anchor_now_covering_forecasts(tmp_path):
    assert errs_with(run(tmp_path, c08(sources_read=[]), dry_run=True), "sources_read is empty")
    ans = c08()
    ans["forecasts"][0] = fc("US10Y", reasoning="The FOMC on 9 Dec is priced for a hike; long yields lag.")
    res = run(tmp_path, ans, dry_run=True)
    assert errs_with(res, "forecast 1 (US10Y) reasoning names 9 Dec"), res["errors"]
    assert errs_with(res, "forecast 1 (US10Y) reasoning cites FOMC")
    ans["time_anchor"] = {"now_utc": T.isoformat(), "events": [{"event": "FOMC decision", "date": "2026-12-09",
                                                                "occurred": False}]}
    assert run(tmp_path, ans, dry_run=True)["ok"]
    ans["forecasts"][0] = fc("US10Y", reasoning="The FOMC decision on 9 Dec was announced as a hike.")
    assert errs_with(run(tmp_path, ans, dry_run=True), "cannot be described as released")
    assert errs_with(run(tmp_path, c08(time_anchor=None), dry_run=True), "time_anchor (C07): required")


def test_budget_status_under_c08(tmp_path):
    path = tmp_path / "r.jsonl"
    run(tmp_path, c08())
    st = J.budget_status(J.load(path), date(2026, 11, 12))
    assert st["risk_used_pct"] == pytest.approx(3.0, abs=1e-3) and not st["flags"]


def test_c08_applies_from_the_11_november_review_only():
    """A 10 Nov discretionary review is judged as before (C06/C07); from 11 Nov it is rejected."""
    old = {"session": "daily_review", "model": "m", "market_summary": "x", "reviews": [],
           "new_positions": [pos(instrument="US10Y", stop=5.10, risk_pct=1.5),
                             pos(instrument="DE10Y", stop=3.50, risk_pct=1.5)],
           "sources_read": SR, "time_anchor": {"now_utc": "2026-11-10T23:07:00Z", "events": []},
           "candidates": [{"instrument": i, "direction": d, "probability": 56, "market_probability": 50,
                           "outcome": o, "opposition": "kept" if o == "opened" else "none", "reason": "ranked on edge"}
                          for i, d, o in (("US10Y", "long", "opened"), ("DE10Y", "long", "opened"),
                                          ("EUR", "long", "not_opened"), ("GOLD", "long", "not_opened"),
                                          ("WTI", "short", "not_opened"))]}
    t10 = datetime(2026, 11, 10, 23, 7, tzinfo=UTC)
    assert J.apply_proposal(old, now=t10, path=None, marks_rows=marks())["ok"]
    res = J.apply_proposal({**old, "time_anchor": {"now_utc": T.isoformat(), "events": []}}, now=T, path=None,
                           marks_rows=marks("2026-11-10"))
    assert not res["ok"] and errs_with(res, "new_positions is not used under C08")


def test_context_shows_the_watchlist_and_the_c08_rules():
    w = J._watchlist_context(marks("2026-11-10"), date(2026, 11, 11))
    assert [x["instrument"] for x in w] == WL and w[0]["mark_date"] == "2026-11-10" and w[0]["question"]


# ----------------------------------------------------------------------------- docs
def test_c08_is_recorded_in_the_config_changes_runbooks_and_fund_docs():
    assert J.C08_FROM == date(2026, 11, 11) and J.C08_NO_TRADE_BAND == 0.25 and J.C08_RISK_PER_POINT == 0.1
    doc = (ROOT / "docs/config_changes.md").read_text(encoding="utf-8")
    assert "| C08 | 2026-11-11 |" in doc and "## C08" in doc and "Approved by Ethan on 2026-11-11" in doc
    for c in ("C05", "C06", "C07"):                      # the superseded rules are marked in their sections
        sec = doc.split(f"## {c} ", 1)[1].split("\n## ", 1)[0]
        assert "Superseded by C08" in sec or "superseded** (" in sec or "are **superseded**" in sec, c
    for f in ("docs/janus/daily_review.md", "docs/janus/quick_check.md", "data/janus/README.md"):
        assert "C08" in (ROOT / f).read_text(encoding="utf-8"), f
    fund = (ROOT / "docs/fund/allocation.md").read_text(encoding="utf-8")
    assert "one call per correlation cluster per non-overlapping 20-trading-day window" in fund      # as amended by C09


def _runbook_example():
    rb = (ROOT / "docs/janus/daily_review.md").read_text(encoding="utf-8")
    return json.loads(rb.split("`/tmp/janus_review.json` (C08 format):\n\n```json\n", 1)[1].split("\n```", 1)[0])


def test_the_runbook_example_passes_the_cli(tmp_path):
    """The C08-format example in docs/janus/daily_review.md, with its placeholders filled and data_failure (which
    does not apply) left out, passes and sets a ten-position book."""
    ex = _runbook_example()
    assert [f["instrument"] for f in ex["forecasts"]] == WL
    assert all(f["p_final"] != 50 and f["p_initial"] != 50 for f in ex["forecasts"])
    assert not set(J.C08_DISCRETIONARY) & set(ex)
    ex.pop("data_failure")
    ex.update(sources_read=SR, model="claude-opus-5-5")
    ex["time_anchor"]["now_utc"] = T.isoformat().replace("+00:00", "Z")
    for f in ex["forecasts"]:
        if f["reasoning"] == "...":
            f["reasoning"] = "The latest data and positioning lean this way."
        if f["opposition"]["case_against"] == "...":
            f["opposition"]["case_against"] = "It is priced, and the trend could turn."
    res = run(tmp_path, ex)
    assert res["ok"], res["errors"]
    assert len(res["opened"]) == 10 and len(res["forecasts"]) == 10


def test_the_cli_dry_run_shows_the_book(tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(c08(now=datetime.now(UTC).replace(microsecond=0))))
    env = {**__import__("os").environ, "EM_MACRO_DATA": str(tmp_path / "no-store"),
           "DATA_REPO_URL": str(tmp_path / "no-such-repo.git")}
    env.pop("DATA_REPO_READ_TOKEN", None)
    out = subprocess.run([sys.executable, "-m", "ledger.janus", "propose", "--file", str(f), "--dry-run"], cwd=ROOT,
                         capture_output=True, text=True, env=env)
    res = json.loads(out.stdout)
    # the real marks decide whether it passes; either way it is judged under C08 and writes nothing
    assert "targets" in res or any("C08" in e for e in res["errors"]), out


# ----------------------------------------------------------------------------- the 10 Nov 23:07 UTC review under C08
REPLAY_NOW = datetime(2026, 11, 10, 23, 13, 29, tzinfo=UTC)          # its decided_at (now_utc 23:12)


def _2307_proposal():
    """The proposal behind records 238-241 (the 10 Nov 23:07 UTC daily review), rebuilt from the chain."""
    recs = {r["seq"]: r for r in _chain_until(241)}
    r = recs[238]
    return {"session": "daily_review", "model": r["model"], "market_summary": r["market_summary"],
            "reviews": [{"id": recs[s]["position_id"], "action": recs[s]["action"], "reasoning": recs[s]["reasoning"]}
                        for s in (239, 240)],
            "new_positions": [], "no_trade_reasoning": recs[241]["reasoning"], "sources_read": r["sources_read"],
            "below_budget": r["below_budget"], "candidates": r["candidates"], "time_anchor": r["time_anchor"]}


def test_the_10_nov_2307_review_replayed_under_c08(tmp_path, monkeypatch):
    """How C08 would have handled the 10 Nov 23:07 UTC review (run record seq 238; J001 and J002 pending at 0.25%
    each, a below_budget reason tied to the FOMC on 9 Dec, candidates at 45-50%). The chain is not edited: the replay
    runs on a copy of records 1-237 with C08 in force on 10 Nov."""
    recs = _chain_until(241)
    assert J.verify(recs)["ok"] and recs[237]["risk_after_pct"] == 0.5
    path = tmp_path / "r.jsonl"
    _write(path, recs[:237])
    monkeypatch.setattr(J, "C08_FROM", date(2026, 11, 10))
    mk = marks("2026-11-09")
    ans = _2307_proposal()
    # 1. As recorded, C08 rejects it: no forecasts, and the discretionary fields it used no longer exist
    res = J.apply_proposal(ans, now=REPLAY_NOW, path=path, marks_rows=mk, dry_run=True)
    assert not res["ok"]
    for field in ("reviews", "below_budget", "candidates"):
        assert errs_with(res, f"{field} is not used under C08"), field
    assert errs_with(res, "forecasts (C08): required")
    # 2. Its own stated views become forecasts (YES = the long side): short US10Y at 45% -> 55; long GB10Y 50; long
    #    JPY 48; short AUD 48 -> 52; long DE10Y 48. EUR, GBP, JP10Y (and BRL, MXN, added by C09) were never considered.
    stated = {c["instrument"]: (c["probability"] if c["direction"] == "long" else 100 - c["probability"], c["reason"])
              for c in ans["candidates"]}
    assert {i: p for i, (p, _) in stated.items()} == {"US10Y": 55, "GB10Y": 50, "JPY": 48, "AUD": 52, "DE10Y": 48}
    opp_us = ("The Opposition (probability the short view is wrong 58%): the hawkish surprise is priced, the move "
              "was a bear flattener, and oil still drives the long end.")
    def forecast(i, p, why):
        return {"instrument": i, "p_initial": p, "p_final": p, "reasoning": why,
                "opposition": {"case_against": opp_us if i == "US10Y" else
                               "No Opposition was run on this candidate in the 10 Nov review (replay).",
                               "model": "claude-opus-5-5"}}
    c08_ans = {k: v for k, v in ans.items() if k not in ("reviews", "below_budget", "candidates", "new_positions",
                                                          "no_trade_reasoning")}
    c08_ans["forecasts"] = [forecast(i, p, why) for i, (p, why) in stated.items()]
    res = J.apply_proposal(c08_ans, now=REPLAY_NOW, path=path, marks_rows=mk, dry_run=True)
    assert errs_with(res, "forecast 2 (GB10Y): p_final is 50, which is not a forecast"), res["errors"]
    assert errs_with(res, "missing JP10Y, EUR, GBP, BRL, MXN")
    # 3. Forced to a side: GB10Y 51 (it leaned to holding J002 long), and the five it never considered
    forced = {"GB10Y": 51, "EUR": 51, "GBP": 49, "JP10Y": 49, "BRL": 51, "MXN": 49}
    why = "Not considered by the 10 Nov review; C08 forces a side (replay)."
    c08_ans["forecasts"] = [forecast(i, forced.get(i, p), w) for i, (p, w) in stated.items() if i != "GB10Y"] + \
        [forecast(i, p, why) for i, p in forced.items()]
    res = J.apply_proposal(c08_ans, now=REPLAY_NOW, path=path, marks_rows=mk)
    assert res["ok"], res["errors"]
    new = J.load(path)[237:]
    # J001 and J002 closed as the closing action (cancelled: neither had filled)
    assert [(r["position_id"], r["action"]) for r in new if r["type"] == "review"] == [("J001", "close"),
                                                                                       ("J002", "close")]
    assert sorted(r["position_id"] for r in new if r["type"] == "cancel") == ["J001", "J002"]
    # ten forecasts logged; ten orders from them at 3.00% at risk (1.7% raw, scaled up to the band) instead of 0.5%
    assert len([r for r in new if r["type"] == "forecast"]) == 10
    opens = {r["instrument"]: r for r in new if r["type"] == "open"}
    assert {i: o["direction"] for i, o in opens.items()} == {
        "US10Y": "long", "JPY": "short", "AUD": "long", "DE10Y": "short", "GB10Y": "long", "EUR": "long",
        "GBP": "short", "JP10Y": "short", "BRL": "long", "MXN": "short"}
    assert opens["US10Y"]["risk_pct"] == pytest.approx(3 * 5 / 17, abs=1e-6)               # 0.88%
    assert opens["GB10Y"]["risk_pct"] == pytest.approx(3 / 17, abs=1e-6)
    assert sum(o["risk_pct"] for o in opens.values()) == pytest.approx(3.0, abs=1e-5)
    assert next(r for r in new if r["type"] == "run")["risk_after_pct"] == pytest.approx(3.0)
    # The Opposition argued against short US10Y; under C08 it is a forecast like any other, logged and sized
    assert opens["US10Y"]["forecast_id"] and J.verify(J.load(path))["ok"]
    # the orders fill at the next official daily marks, and every forecast resolves 20 trading days later
    J.process(J.load(path), mk + day_marks("2026-11-10") + day_marks("2026-11-11"), date(2026, 11, 12), path)
    assert all(p["status"] == "open" for p in book(path).values()) and len(book(path)) == 10
