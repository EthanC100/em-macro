"""Tests for the Ledger automation: marks and live P&L, the auto-resolver (stop and horizon
closes, mechanical and event forecast resolution), the Risk Manager, the screener and the
to-do page. Made-up data only; no network."""
import csv
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from ledger import intake, marks, resolve, resolver_api, schema, scoring

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = marks.load_registry()


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write(path, rows, columns):
    intake.write_rows(Path(path), rows, columns)


def _decision(**over):
    d = {c: "" for c in schema.DECISION_COLUMNS}
    d.update(dict(id="D010", date="2026-11-01", country="Brazil", instrument="USD/BRL", action="Buy", size_pct="1.0",
                  probability="60", horizon="2026-12-01", entry_trigger="5.40", stop="exit if USD/BRL closes above 5.70",
                  entry_level="5.40", thesis="t", key_factors="k", change_mind="c", vs_consensus="v", status="open",
                  logged_at="2026-11-01"))
    d.update(over)
    return d


def _forecast(**over):
    f = {c: "" for c in schema.FORECAST_COLUMNS}
    f.update(dict(id="F010", date="2026-11-01", question="Does the ECB cut in December 2026?", country="Euro area",
                  my_prob="70", market_prob="55", market_source="Polymarket", claude_prob="60",
                  resolution_date="2026-12-18", resolution_source="ECB press release", status="open",
                  logged_at="2026-11-01"))
    f.update(over)
    return f


def _mark(instrument, day, value, unit="BRL per USD", freq="daily"):
    return {"date": day, "instrument": instrument, "value": str(value), "unit": unit, "frequency": freq,
            "source": "test", "source_url": "https://example.org/data", "fetched_at": f"{day}T06:00:00+00:00", "note": ""}


@pytest.fixture
def root(tmp_path):
    (tmp_path / "data").mkdir()
    shutil.copytree(ROOT / "data/ledger", tmp_path / "data/ledger")
    (tmp_path / "data/ledger/marks.csv").unlink(missing_ok=True)
    for p in ("api_log.csv", "automation_log.csv"):
        (tmp_path / "data/ledger" / p).unlink(missing_ok=True)
    (tmp_path / "results/systematic").mkdir(parents=True)
    shutil.copy(ROOT / "results/systematic/positions.csv", tmp_path / "results/systematic/positions.csv")
    return tmp_path


# ----------------------------------------------------------------------------- marks
def test_registry_covers_the_v1_universe():
    design = json.loads((ROOT / "results/systematic/fit/frozen_design.json").read_text())
    universe = set(design["instruments"]["fx"]) | set(design["instruments"]["bond"])
    assert universe <= {r["instrument"] for r in REGISTRY}
    for r in REGISTRY:
        assert r["source"] in marks.FETCHERS or r["source"] == "spread"
        assert r["frequency"] in ("daily", "monthly")


def test_instrument_matching_from_free_text():
    assert marks.match_instrument("FR-DE 10y OAT-Bund spread", REGISTRY)["instrument"] == "FR-DE"
    assert marks.match_instrument("USD/BRL", REGISTRY)["instrument"] == "BRL"
    assert marks.match_instrument("Mexico 10y local bond (MX10Y)", REGISTRY)["instrument"] == "MX10Y"
    assert marks.match_instrument("the 10y Bund", REGISTRY)["instrument"] == "DE10Y"
    assert marks.match_instrument("gold", REGISTRY) is None


def test_fetchers_parse_source_formats():
    fred = b"observation_date,DEXBZUS\n2026-11-02,5.40\n2026-11-03,.\n"
    assert marks.fetch_fred("DEXBZUS", get=lambda u, **k: fred)[:2] == (date(2026, 11, 2), 5.40)
    bcb = json.dumps([{"data": "02/11/2026", "valor": "5.4"}, {"data": "03/11/2026", "valor": "5.5"}]).encode()
    assert marks.fetch_bcb_sgs("1", get=lambda u, **k: bcb)[:2] == (date(2026, 11, 3), 5.5)

    def ecb(url, **k):
        if "D.USD." in url:
            return b"KEY,TIME_PERIOD,OBS_VALUE\nx,2026-11-03,1.10\n"
        return b"KEY,TIME_PERIOD,OBS_VALUE\nx,2026-11-03,5.50\n"
    d, v, _ = marks.fetch_ecb_exr("BRL", get=ecb)
    assert (d, v) == (date(2026, 11, 3), 5.0)
    boe = b"DATE,IUDMNPY\n30 Oct 2026,5.25\n02 Nov 2026,5.17\n"
    assert marks.fetch_boe("IUDMNPY", get=lambda u, **k: boe, today=date(2026, 11, 4))[:2] == (date(2026, 11, 2), 5.17)
    bb = "﻿\"\",BBSIS.X,FLAGS\n\"\",desc,\n2026-11-02,3.37,\n2026-11-03,3.38,\n2026-11-04,.,No value\n".encode()
    assert marks.fetch_bundesbank("X", get=lambda u, **k: bb)[:2] == (date(2026, 11, 3), 3.38)
    bde = ("a\nb\n\"ALIAS\",\"TI_1_3.1\",\"TI_1_3.11\"\nd\ne\nf\n30 OCT 2026,1,4.053\n31 OCT 2026,_,_\n02 NOV 2026,1,3.927\n"
           "FUENTE,x,y\n").encode("latin-1")
    assert marks.fetch_bde("ti_1_3:TI_1_3.11", get=lambda u, **k: bde)[:2] == (date(2026, 11, 2), 3.927)


def test_spread_marks_and_fallback(tmp_path):
    reg = [{"instrument": "A10Y", "unit": "% yield", "frequency": "daily", "source": "fred", "source_id": "A",
            "fallback_source": "", "fallback_id": ""},
           {"instrument": "B10Y", "unit": "% yield", "frequency": "daily", "source": "fred", "source_id": "B",
            "fallback_source": "fred", "fallback_id": "B2"},
           {"instrument": "A-B", "unit": "bp", "frequency": "daily", "source": "spread", "source_id": "A10Y-B10Y",
            "fallback_source": "", "fallback_id": ""}]

    def get(url, **k):
        if "id=A" in url:
            return b"d,A\n2026-11-03,4.00\n"
        if "id=B2" in url:
            return b"d,B\n2026-11-02,3.00\n"
        raise RuntimeError("down")
    out = marks.fetch_all(reg, date(2026, 11, 4), get=get)
    by = {m["instrument"]: m for m in out}
    assert by["B10Y"]["value"] == "3" and by["B10Y"]["note"].startswith("fallback fred B2")
    assert by["A-B"]["value"] == "100" and by["A-B"]["date"] == "2026-11-02"
    # a source that fails with no fallback keeps the previous mark
    prev = {"A10Y": _mark("A10Y", "2026-11-01", 3.9, "% yield")}
    out = marks.fetch_all(reg[:1], date(2026, 11, 4), get=lambda u, **k: (_ for _ in ()).throw(RuntimeError("x")), previous=prev)
    assert out[0]["value"] == "3.9" and "kept previous mark" in out[0]["note"]
    # merge: one row per instrument and date
    p = tmp_path / "marks.csv"
    assert marks.write_marks([_mark("BRL", "2026-11-03", 5.4), _mark("BRL", "2026-11-03", 5.4)], p) == 1
    assert marks.write_marks([_mark("BRL", "2026-11-03", 5.5), _mark("BRL", "2026-11-04", 5.6)], p) == 2
    assert [r["value"] for r in marks.read_marks(p)] == ["5.5", "5.6"]
    assert marks.latest_marks(p)["BRL"]["date"] == "2026-11-04"


def test_live_pnl_from_marks():
    d = _decision()
    latest = {"BRL": _mark("BRL", "2026-11-03", 5.25)}
    lm = marks.live_mark(d, REGISTRY, latest)
    # buy at 5.40, stop 5.70 (above): a fall to 5.25 earns 1.0 x 0.15 / 0.30 = +0.5%
    assert lm["mark_instrument"] == "BRL" and lm["live_pnl_pct"] == 0.5 and lm["stop_distance"] == -0.45
    assert scoring.pnl_at_level(d, 5.85) == -1.5
    # a mark older than the decision gives no P&L
    lm = marks.live_mark(d, REGISTRY, {"BRL": _mark("BRL", "2026-10-15", 5.25)})
    assert lm["live_pnl_pct"] is None and "predates" in lm["mark_note"]
    # no entry level: no P&L, but the mark is shown
    lm = marks.live_mark(_decision(entry_level=""), REGISTRY, latest)
    assert lm["live_pnl_pct"] is None and lm["mark"] == 5.25
    assert marks.live_mark(_decision(action="No trade", size_pct="0"), REGISTRY, latest)["live_pnl_pct"] is None


# ----------------------------------------------------------------------------- stop and horizon closes
def test_stop_rule_from_entry_or_wording():
    assert resolve.stop_rule(_decision()) == (5.7, "above")
    assert resolve.stop_rule(_decision(entry_level="", stop="exit if the spread tightens to 115bp")) == (115.0, "below")
    assert resolve.stop_rule(_decision(entry_level="159", stop="tightens to 115bp")) == (115.0, "below")
    assert resolve.stop_rule(_decision(entry_level="", stop="View is wrong if USD/BRL closes above 5.70")) == (5.7, "above")
    assert resolve.stop_rule(_decision(entry_level="", stop="stop at 5.70")) == (5.7, None)
    assert resolve.stop_hit(_decision(), 5.71) is True and resolve.stop_hit(_decision(), 5.69) is False


def test_stop_close_uses_first_crossing_mark():
    d = _decision()
    mk = [_mark("BRL", "2026-11-02", 5.50), _mark("BRL", "2026-11-05", 5.75), _mark("BRL", "2026-11-06", 5.60)]
    changed, issues, log = resolve.process_decisions([d], mk, REGISTRY, date(2026, 11, 7))
    assert changed and not issues
    assert d["status"] == "resolved" and d["outcome"] == "wrong" and d["exit_price"] == "5.75"
    # 1.0 x (5.75 - 5.40) x (-1) / 0.30 = -1.167
    assert d["pnl_pct"] == "-1.167" and d["resolved_date"] == "2026-11-07"
    assert d["resolution_note"].startswith("Auto-resolved (stop hit)") and "https://example.org/data" in d["resolution_note"]
    assert scoring.score_decision(d)["brier"] == 0.36      # p 60% and wrong


def test_stop_close_without_entry_level_books_the_size_at_risk():
    d = _decision(entry_level="")
    changed, _, _ = resolve.process_decisions([d], [_mark("BRL", "2026-11-05", 5.80)], REGISTRY, date(2026, 11, 6))
    assert changed and d["outcome"] == "wrong" and d["pnl_pct"] == "-1" and "size at risk" in d["resolution_note"]


def test_marks_before_the_decision_never_close_it():
    d = _decision()
    changed, issues, _ = resolve.process_decisions([d], [_mark("BRL", "2026-10-20", 5.90)], REGISTRY, date(2026, 11, 5))
    assert not changed and not issues and d["status"] == "open"


def test_monthly_or_carried_marks_never_stop_or_close_a_position():
    # D001's failure mode: a monthly average below the stop must not close the position
    d = _decision(instrument="FR-DE 10y OAT-Bund spread", action="Sell", entry_level="159", stop="115",
                  date="2026-10-30", horizon="2027-04-18")
    monthly = _mark("FR-DE", "2026-10-31", 96.7, "bp", "monthly")
    carried = {**_mark("FR-DE", "2026-11-03", 100.0, "bp"), "note": "kept previous mark; riksbank down"}
    changed, issues, log = resolve.process_decisions([d], [monthly, carried], REGISTRY, date(2026, 11, 6))
    assert not changed and not issues and d["status"] == "open" and any("ignored" in x for x in log)
    # and past the horizon with only monthly marks: an issue, not a close
    d2 = _decision(instrument="FR-DE spread", action="Sell", entry_level="159", stop="115", date="2026-10-30",
                   horizon="2026-11-05")
    changed, issues, _ = resolve.process_decisions([d2], [monthly], REGISTRY, date(2026, 11, 6))
    assert not changed and issues and d2["status"] == "open"
    # a first-hand daily mark through the stop does close it
    changed, _, _ = resolve.process_decisions([d], [_mark("FR-DE", "2026-11-05", 114.0, "bp")], REGISTRY, date(2026, 11, 6))
    assert changed and d["outcome"] == "wrong"
    assert not marks.mark_can_act(monthly) and not marks.mark_can_act(carried)
    assert marks.mark_can_act(_mark("FR-DE", "2026-11-05", 150.0, "bp"))


def test_riksbank_and_jgb_parsers():
    rb = json.dumps([{"date": "2026-11-03", "value": 4.9509}, {"date": "2026-11-04", "value": 4.7823}]).encode()
    assert marks.fetch_riksbank("FRGVB10Y", get=lambda u, **k: rb)[:2] == (date(2026, 11, 4), 4.7823)
    jgb = ("Interest Rate,,\nDate,1Y,10Y\n2026/11/4,1.6,2.81\n2026/11/5,1.658,2.806\n,,\n").encode()
    assert marks.fetch_mof_jgb("10Y", get=lambda u, **k: jgb)[:2] == (date(2026, 11, 5), 2.806)
    reg = {r["instrument"]: r for r in REGISTRY}
    assert reg["FR-DE"]["frequency"] == "daily" and reg["FR-DE"]["source_id"] == "FR10Y-DE10YBM"
    assert not reg["FR-DE"]["fallback_source"]       # never falls back to a monthly average


def test_horizon_close_scores_by_pnl_sign():
    d = _decision()
    mk = [_mark("BRL", "2026-11-20", 5.30), _mark("BRL", "2026-12-01", 5.20)]
    changed, issues, _ = resolve.process_decisions([d], mk, REGISTRY, date(2026, 11, 30))
    assert not changed                                   # horizon not reached yet
    changed, issues, _ = resolve.process_decisions([d], mk, REGISTRY, date(2026, 12, 1))
    assert changed and d["outcome"] == "right" and d["exit_price"] == "5.2" and d["pnl_pct"] == "0.667"
    assert "horizon reached" in d["resolution_note"]
    d = _decision()
    resolve.process_decisions([d], [_mark("BRL", "2026-12-01", 5.55)], REGISTRY, date(2026, 12, 2))
    assert d["outcome"] == "wrong" and d["pnl_pct"] == "-0.5"
    d = _decision()
    resolve.process_decisions([d], [_mark("BRL", "2026-12-01", 5.401)], REGISTRY, date(2026, 12, 2))
    assert d["outcome"] == "scratched"


def test_horizon_close_of_a_no_trade_and_unresolvable_cases():
    nt = _decision(id="D011", action="No trade", size_pct="0", entry_level="", stop="View is wrong if USD/BRL closes above 5.70")
    changed, issues, _ = resolve.process_decisions([nt], [_mark("BRL", "2026-11-20", 5.50)], REGISTRY, date(2026, 12, 1))
    assert changed and nt["outcome"] == "right" and nt["pnl_pct"] == "" and "no-trade view held" in nt["resolution_note"]
    nt = _decision(id="D011", action="No trade", size_pct="0", entry_level="", stop="View is wrong if USD/BRL closes above 5.70")
    resolve.process_decisions([nt], [_mark("BRL", "2026-11-20", 5.80)], REGISTRY, date(2026, 11, 21))
    assert nt["outcome"] == "wrong" and nt["pnl_pct"] == ""
    # a position with no entry level at the horizon: [RESOLVE?] issue, nothing written
    d = _decision(entry_level="")
    changed, issues, _ = resolve.process_decisions([d], [_mark("BRL", "2026-11-20", 5.50)], REGISTRY, date(2026, 12, 1))
    assert not changed and issues[0]["title"] == "[RESOLVE?] D010" and "entry level" in issues[0]["body"]
    # an instrument not in the registry
    d = _decision(instrument="gold")
    changed, issues, _ = resolve.process_decisions([d], [], REGISTRY, date(2026, 12, 1))
    assert not changed and "matches nothing" in issues[0]["body"]


def test_resolve_form_overrides_an_automatic_resolution(root):
    d = _decision()
    _write(root / "data/ledger/decisions.csv", _rows(root / "data/ledger/decisions.csv") + [d], schema.DECISION_COLUMNS)
    (root / "data/ledger/marks.csv").write_text("")
    marks.write_marks([_mark("BRL", "2026-11-05", 5.80)], root / "data/ledger/marks.csv")
    res = resolve.run(today=date(2026, 11, 6), root=root)
    # the seed no-trade D002 (view wrong if USD/BRL closes above 5.70) is closed by the same mark
    assert res["closed"] == ["D002", "D010"]
    d002 = next(r for r in _rows(root / "data/ledger/decisions.csv") if r["id"] == "D002")
    assert d002["outcome"] == "wrong" and d002["pnl_pct"] == ""
    row = next(r for r in _rows(root / "data/ledger/decisions.csv") if r["id"] == "D010")
    assert row["status"] == "resolved" and row["outcome"] == "wrong"
    log = _rows(root / "data/ledger/automation_log.csv")
    assert log[-1]["id"] == "D010" and log[-1]["action"] == "closed wrong"
    body = "### Decision or forecast id\n\nD010\n\n### Outcome\n\nRight (decision)\n\n### Exit price or result\n\n5.20\n\n### Note (optional)\n\nclosed early by hand\n"
    out = intake.process("resolve", body, 99, date(2026, 11, 8), root)
    assert out["ok"] and "Overrides the automatic resolution" in out["comment"]
    row = next(r for r in _rows(root / "data/ledger/decisions.csv") if r["id"] == "D010")
    assert row["outcome"] == "right" and row["exit_price"] == "5.20" and "Overrides" in row["resolution_note"]
    # a manual resolution is final
    assert not intake.process("resolve", body, 100, date(2026, 11, 9), root)["ok"]
    # the resolver never touches a resolved row
    marks.write_marks([_mark("BRL", "2026-11-10", 5.90)], root / "data/ledger/marks.csv")
    assert resolve.run(today=date(2026, 11, 11), root=root)["closed"] == []


# ----------------------------------------------------------------------------- forecast resolution
def test_classification_and_rate_question_parsing():
    assert resolve.classify_forecast(_forecast(), REGISTRY) == "rate"
    assert resolve.classify_forecast(_forecast(question="USD/BRL closes above 5.70 on 24 Dec 2026", resolution_source="BCB PTAX"), REGISTRY) == "level"
    assert resolve.classify_forecast(_forecast(question="Republicans keep control of the US Senate", resolution_source="AP race call"), REGISTRY) == "event"
    q = resolve.parse_rate_question("Does Copom cut the Selic by 50bp in December 2026?")
    assert q["area"] == "BR" and q["kind"] == "cut" and q["size_bp"] == 50 and q["month"] == (12, 2026)
    assert resolve.parse_rate_question("Banxico holds in February")["kind"] == "hold"


def _bis(points):
    body = "FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n" + "".join(f"D,XM,{d},{v}\n" for d, v in points)
    return lambda url, **k: body.encode()


def test_rate_question_resolves_from_bis_data():
    f = _forecast()
    cut = _bis([("2026-11-30", 2.5), ("2026-12-17", 2.5), ("2026-12-18", 2.25), ("2026-12-19", 2.25)])
    r = resolve.resolve_rate_question(f, date(2026, 12, 20), get=cut)
    assert r["status"] == "resolved" and r["outcome"] == "yes" and "-25bp" in r["summary"]
    hold = _bis([("2026-11-30", 2.5), ("2026-12-18", 2.5), ("2026-12-19", 2.5)])
    assert resolve.resolve_rate_question(f, date(2026, 12, 20), get=hold)["outcome"] == "no"
    # a size in the question must match
    f50 = _forecast(question="Does the ECB cut by 50bp in December 2026?")
    assert resolve.resolve_rate_question(f50, date(2026, 12, 20), get=cut)["outcome"] == "no"
    # data not yet published: wait
    stale = _bis([("2026-11-30", 2.5), ("2026-12-10", 2.5)])
    assert resolve.resolve_rate_question(f, date(2026, 12, 20), get=stale)["status"] == "waiting"


def test_level_question_resolves_from_marks():
    f = _forecast(question="USD/BRL closes above 5.70 on 24 December 2026", resolution_source="BCB PTAX", resolution_date="2026-12-24")
    mk = [_mark("BRL", "2026-12-23", 5.75)]
    r = resolve.resolve_level_question(f, mk, REGISTRY, date(2026, 12, 26))
    assert r["status"] == "resolved" and r["outcome"] == "yes" and r["sources"][0]["url"] == "https://example.org/data"
    assert resolve.resolve_level_question(f, [_mark("BRL", "2026-12-24", 5.60)], REGISTRY, date(2026, 12, 26))["outcome"] == "no"
    assert resolve.resolve_level_question(f, [_mark("BRL", "2026-12-01", 5.60)], REGISTRY, date(2026, 12, 26))["status"] == "waiting"
    f2 = _forecast(question="OAT-Bund spread wider than 150bp at end-December 2026", resolution_source="ECB", resolution_date="2026-12-31")
    r = resolve.resolve_level_question(f2, [_mark("FR-DE", "2026-12-31", 140, "bp", "monthly")], REGISTRY, date(2027, 1, 2))
    assert r["outcome"] == "no"


def _answer(outcome, sources):
    return lambda prompt: {"text": "Here you go:\n" + json.dumps({"outcome": outcome, "confidence": 0.9, "summary": "AP called it on 4 Nov 2026.", "sources": sources}),
                           "usage": {"input_tokens": 1000, "output_tokens": 200}, "searches": 3, "model": "claude-sonnet-5-5"}


AP = {"organisation": "Associated Press", "url": "https://apnews.com/article/senate-2026", "date": "2026-11-04", "quote": "AP called the race"}
REUTERS = {"organisation": "Reuters", "url": "https://www.reuters.com/world/us/senate", "date": "2026-11-04", "quote": "AP projected"}
AP_HUB = {"organisation": "AP News", "url": "https://apnews.com/hub/senate", "date": "2026-11-04", "quote": "same org again"}
AP_MIRROR = {"organisation": "The Associated Press", "url": "https://news.yahoo.com/ap-senate", "date": "2026-11-04", "quote": "AP wire"}


def test_event_resolution_needs_two_independent_sources():
    cfg = marks.CONFIG
    ok = resolver_api.resolve_event("q", "2026-11-10", "AP race call", "United States", "2026-11-11", cfg, "k", ask=_answer("yes", [AP, REUTERS]))
    assert ok["status"] == "resolved" and ok["outcome"] == "yes" and len(ok["sources"]) == 2
    same_org = resolver_api.resolve_event("q", "2026-11-10", "AP race call", "", "2026-11-11", cfg, "k", ask=_answer("yes", [AP, AP_HUB]))
    assert same_org["status"] == "unresolved" and "only 1 independent source" in same_org["reason"]
    same_name = resolver_api.resolve_event("q", "2026-11-10", "AP race call", "", "2026-11-11", cfg, "k", ask=_answer("no", [AP, AP_MIRROR]))
    assert same_name["status"] == "unresolved"
    unres = resolver_api.resolve_event("q", "2026-11-10", "AP race call", "", "2026-11-11", cfg, "k", ask=_answer("unresolved", [AP, REUTERS]))
    assert unres["status"] == "unresolved" and "not settled" in unres["reason"]
    nokey = resolver_api.resolve_event("q", "2026-11-10", "AP race call", "", "2026-11-11", cfg, None)
    assert nokey["status"] == "no_key"
    bad = resolver_api.resolve_event("q", "2026-11-10", "AP race call", "", "2026-11-11", cfg, "k", ask=lambda p: {"text": "no json here"})
    assert bad["status"] == "unresolved" and "no JSON" in bad["reason"]
    err = resolver_api.resolve_event("q", "2026-11-10", "AP race call", "", "2026-11-11", cfg, "k", ask=lambda p: (_ for _ in ()).throw(RuntimeError("boom")))
    assert err["status"] == "error" and "boom" in err["reason"]
    assert resolver_api.registrable_domain("https://www.bbc.co.uk/news/x") == "bbc.co.uk"
    assert resolver_api.registrable_domain("https://apnews.com/a") == "apnews.com"


def test_event_forecasts_resolve_score_and_cap(root):
    fc = root / "data/ledger/forecasts.csv"
    rows = _rows(fc)
    ev = _forecast(id="F010", question="Republicans keep control of the US Senate", resolution_source="AP race call",
                   resolution_date="2026-11-10", my_prob="45", market_prob="30", claude_prob="41")
    _write(fc, rows + [ev], schema.FORECAST_COLUMNS)
    res = resolve.run(today=date(2026, 11, 11), root=root, api_key="k", ask=_answer("yes", [AP, REUTERS]))
    assert "F010" in res["resolved"]
    row = next(r for r in _rows(fc) if r["id"] == "F010")
    assert row["status"] == "resolved" and row["outcome"] == "yes" and row["result"].startswith("Auto-resolved yes")
    assert "https://apnews.com/article/senate-2026" in row["result"] and "reuters.com" in row["result"]
    sc = scoring.score_forecast(row)
    assert sc["brier_me"] == 0.3025 and sc["brier_market"] == 0.49 and sc["brier_claude"] == 0.3481
    api = _rows(root / "data/ledger/api_log.csv")
    assert len(api) == 6 and api[-1]["forecast_id"] == "F010" and api[-1]["status"] == "resolved"   # F001-F005 too
    # the seed forecasts (AP race call) were asked as well, and the issues carry the sources found
    assert all(r["status"] == "resolved" for r in _rows(fc))
    # the daily cap: with 6 calls logged and a cap of 10, four more are allowed today
    more = [_forecast(id=f"F0{n}", question=f"Event {n}", resolution_source="AP", resolution_date="2026-11-10") for n in range(20, 26)]
    _write(fc, _rows(fc) + more, schema.FORECAST_COLUMNS)
    res = resolve.run(today=date(2026, 11, 11), root=root, api_key="k", ask=_answer("yes", [AP, REUTERS]))
    assert len(res["resolved"]) == 4 and len(res["issues"]) == 2
    assert all("daily cap" in i["body"] for i in res["issues"])
    assert resolve.api_calls_today(date(2026, 11, 11), root / "data/ledger/api_log.csv") == 10


def test_event_forecast_without_key_opens_an_issue_and_nothing_fails(root):
    res = resolve.run(today=date(2026, 11, 11), root=root, api_key=None)
    assert res["resolved"] == [] and [i["title"] for i in res["issues"]] == [f"[RESOLVE?] F00{n}" for n in range(1, 6)]
    assert all("ANTHROPIC_API_KEY" in i["body"] and "Resolve form" in i["body"] for i in res["issues"])
    assert all(r["status"] == "open" for r in _rows(root / "data/ledger/forecasts.csv"))
    assert not (root / "data/ledger/api_log.csv").exists()
    log = _rows(root / "data/ledger/automation_log.csv")
    assert len(log) == 5 and log[0]["action"] == "[RESOLVE?]"


def test_unconfirmed_event_opens_issue_with_findings(root):
    fc = root / "data/ledger/forecasts.csv"
    _write(fc, [_forecast(id="F001", question="X wins", resolution_source="AP race call", resolution_date="2026-11-10")], schema.FORECAST_COLUMNS)
    res = resolve.run(today=date(2026, 11, 11), root=root, api_key="k", ask=_answer("yes", [AP, AP_HUB]))
    assert res["resolved"] == [] and len(res["issues"]) == 1
    body = res["issues"][0]["body"]
    assert "only 1 independent source" in body and "apnews.com/hub/senate" in body and "AP called it" in body
    assert _rows(fc)[0]["status"] == "open"
    # mechanical questions never call the API
    _write(fc, [_forecast(id="F002")], schema.FORECAST_COLUMNS)
    called = []
    res = resolve.run(today=date(2026, 12, 20), root=root, api_key="k", ask=lambda p: called.append(p),
                      get=_bis([("2026-11-30", 2.5), ("2026-12-18", 2.25), ("2026-12-19", 2.25)]))
    assert called == [] and res["resolved"] == ["F002"]
    row = _rows(fc)[0]
    assert row["outcome"] == "yes" and "BIS" in row["result"] and "stats.bis.org" in row["result"]


# ----------------------------------------------------------------------------- Risk Manager
from ledger import risk  # noqa: E402


def _body(**over):
    fields = dict(Date="2026-11-04", Country="Mexico", Instrument="MX10Y", Action="Buy", **{"Size (% of account at risk)": "1.5"},
                  **{"Position type": "Continuous position", "Probability my view is right": "62", "Horizon (date)": "2027-01-15"},
                  **{"Entry trigger": "Buy at 9.20% yield", "Stop / exit if wrong": "Exit if the 10y yield rises above 9.80"},
                  Thesis="Banxico cuts faster than priced.", **{"Key factors": "Inflation; Fed.", "What would change my mind": "A hawkish turn.",
                  "How this differs from market consensus": "Market prices two cuts; I expect four."})
    fields.update(over)
    return "".join(f"### {k}\n\n{v}\n\n" for k, v in fields.items())


def test_risk_manager_rejections(root):
    today = date(2026, 11, 4)
    ok = intake.process("decision", _body(), 1, today, root)
    assert ok["ok"] and ok["risk_comment"].startswith("### Risk Manager: passed")
    assert "✅ Stop has a numeric level: 9.8" in ok["risk_comment"] and "✅ Continuous position risks at most 2%" in ok["risk_comment"]
    assert _rows(root / "data/ledger/decisions.csv")[-1]["position_type"] == "continuous"
    assert _rows(root / "data/ledger/decisions.csv")[-1]["entry_level"] == "9.2"
    # no numeric stop level
    r = intake.process("decision", _body(**{"Stop / exit if wrong": "exit if it feels wrong"}), 2, today, root)
    assert not r["ok"] and "numeric price or yield level" in r["comment"] and "Risk Manager: rejected" in r["risk_comment"]
    # a continuous position above 2%
    r = intake.process("decision", _body(**{"Size (% of account at risk)": "2.5"}), 3, today, root)
    assert not r["ok"] and "at most 2%" in r["comment"]
    # an event bet must be exactly half of quarter-Kelly: 0.125 x (2 x 0.62 - 1) = 3.0%
    assert schema.kelly_size_pct(62) == 3.0
    r = intake.process("decision", _body(**{"Position type": "Event bet"}), 4, today, root)
    assert not r["ok"] and "half of quarter-Kelly" in r["comment"] and "3% of account at 62%" in r["comment"]
    r = intake.process("decision", _body(**{"Position type": "Event bet", "Size (% of account at risk)": "3.0"}), 5, today, root)
    assert r["ok"] and _rows(root / "data/ledger/decisions.csv")[-1]["position_type"] == "event"
    assert "✅ Event bet sized at half of quarter-Kelly" in r["risk_comment"]
    # an event bet at 50% or less has no edge
    r = intake.process("decision", _body(**{"Position type": "Event bet", "Probability my view is right": "45",
                                            "Size (% of account at risk)": "1"}), 6, today, root)
    assert not r["ok"] and "no edge" in r["comment"]
    # a no-trade with a numeric stop passes whatever the type
    r = intake.process("decision", _body(Action="No trade", **{"Size (% of account at risk)": "0", "Position type": "Event bet"}), 7, today, root)
    assert r["ok"] and _rows(root / "data/ledger/decisions.csv")[-1]["position_type"] == ""
    assert len(_rows(root / "data/ledger/decisions.csv")) == 5


def test_risk_manager_flags_overlap_and_catalysts(root):
    today = date(2026, 11, 4)
    # the algorithm is short MXN and long MX10Y (positions.csv as committed): a Mexico decision overlaps
    rm = risk.risk_check({c: "" for c in schema.DECISION_COLUMNS} | dict(
        date="2026-11-04", country="Mexico", instrument="MX10Y", action="Buy", size_pct="1.5", probability="62",
        horizon="2027-01-15", stop="above 9.80", thesis="t"), root, today)
    assert rm["ok"] and any("long MX10Y" in f and "same instrument" in f for f in rm["flags"])
    assert any("short MXN" in f and "same currency (MXN)" in f for f in rm["flags"])
    # France shares the euro with the algorithm's short EUR; no France position otherwise
    rm = risk.risk_check({c: "" for c in schema.DECISION_COLUMNS} | dict(
        date="2026-11-04", country="France", instrument="FR-DE 10y OAT-Bund spread", action="Sell", size_pct="1",
        probability="65", horizon="2027-04-18", stop="tightens to 115bp", thesis="t"), root, today)
    assert [f for f in rm["flags"] if "Overlap" in f] == [f for f in rm["flags"] if "short EUR" in f and "same currency (EUR)" in f]
    assert "monthly rebalance" in rm["comment"] and "D001" not in rm["comment"]      # own horizon excluded
    # a same-country catalyst inside the holding period is flagged; outside it is not
    (root / "data/events").mkdir()
    (root / "data/events/upcoming_events.csv").write_text(
        "iso3,country,date,event_type,subtype,description,outcome,source,notes\n"
        "ESP,Spain,2026-11-29,election,general,Spanish snap general election,,x,\n")
    (root / "data/events/rating_calendar.csv").write_text(
        "iso3,country,date,agency,description,source\nESP,Spain,2026-12-11,Fitch,scheduled sovereign review,x\n")
    rec = {c: "" for c in schema.DECISION_COLUMNS} | dict(
        date="2026-11-04", country="Spain", instrument="ES-DE", action="Buy", size_pct="1", probability="60",
        horizon="2026-12-15", stop="widens above 80bp", thesis="t")
    rm = risk.risk_check(rec, root, today)
    assert rm["ok"] and [c["label"] for c in rm["catalysts"]] == ["Spanish snap general election", "Fitch scheduled sovereign review"]
    assert sum("Catalyst in the holding period" in f for f in rm["flags"]) == 2
    rm = risk.risk_check(rec | {"horizon": "2026-11-20"}, root, today)
    assert rm["catalysts"] == [] and "No same-country catalyst" in rm["comment"]
    # an instrument outside the registry is still checked, by country only
    rm = risk.risk_check(rec | {"instrument": "Spanish equities (IBEX)", "stop": "below 11000"}, root, today)
    assert rm["ok"] and rm["scope"]["iso3"] == "ESP" and "not in the registry" in rm["comment"] and len(rm["catalysts"]) == 2


def test_entry_level_from_trigger():
    f = intake._entry_level_from_trigger
    assert f("Buy at 9.20% yield", {}) == "9.2"
    assert f("Sell at market; entry level 159bp", {}) == "159"
    assert f("At market on the decision date; add on a dip", {}) == ""
    assert f("Reassess if USD/BRL trades below 5.15", {}) == ""


# ----------------------------------------------------------------------------- screener
from ledger import screener  # noqa: E402


def _toy_inputs():
    import numpy as np
    import pandas as pd
    months = pd.period_range("2023-01", "2026-10", freq="M")
    rng = np.random.default_rng(0)
    out = {"months": months}
    for book, names in (("fx", ["BRL", "MXN", "TRY", "EUR"]), ("bond", ["MX10Y", "BR10Y", "FR-DE", "DE10Y"])):
        ret = pd.DataFrame(rng.normal(0, 0.02, (len(months), len(names))), index=months, columns=names)
        ret.iloc[-1, 0] = 0.09                                  # the first instrument jumps > 2 sigma
        carry = pd.DataFrame(rng.normal(2, 1, (len(months), len(names))), index=months, columns=names)
        value = pd.DataFrame(rng.normal(0, 1, (len(months), len(names))), index=months, columns=names)
        if book == "bond":
            ret.iloc[-1, 2] = carry.iloc[-1, 2] = value.iloc[-1, 2] = np.nan     # FR-DE has no October data
        out[book] = {"ret": ret, "carry": carry, "value": value}
    return out


def test_screener_compute_ranks_positions_moves_and_catalysts():
    inp = _toy_inputs()
    positions = [{"instrument": "MX10Y", "side": "long", "size_pct_of_capital": "125.85", "risk_share_pct": "19.4"},
                 {"instrument": "EUR", "side": "short", "size_pct_of_capital": "-52.41", "risk_share_pct": "10.2"}]
    panel = [{"iso3": "BRA", "month": "2026-10", "policy_rate": "13.75", "cpi_yoy": "4.5", "y10": "13.5"},
             {"iso3": "MEX", "month": "2026-09", "policy_rate": "6.5", "cpi_yoy": "3.5", "y10": "9.4"}]
    cal = [{"date": date(2026, 11, 29), "kind": "election", "iso3": "ESP", "country": "Spain", "label": "Spanish general election"},
           {"date": date(2026, 11, 27), "kind": "rating review", "iso3": "FRA", "country": "France", "label": "S&P review"},
           {"date": date(2028, 1, 1), "kind": "election", "iso3": "FRA", "country": "France", "label": "too far away"}]
    res = screener.compute(inp, positions, panel, REGISTRY, cal, date(2026, 11, 4), us_real_rate=-0.12)
    rows = {r["instrument"]: r for r in res["rows"]}
    assert res["as_of"] == "2026-10" and len(res["rows"]) == 8
    fx = [r for r in res["rows"] if r["book"] == "fx"]
    assert sorted(r["rank_composite"] for r in fx) == [1, 2, 3, 4] and sorted(r["rank_carry"] for r in fx) == [1, 2, 3, 4]
    assert max(fx, key=lambda r: r["carry"])["rank_carry"] == 1
    assert rows["MX10Y"]["position"] == "long" and rows["MX10Y"]["size_pct_of_capital"] == 125.85
    assert rows["EUR"]["position"] == "short" and rows["BRL"]["position"] == "none"
    assert rows["BRL"]["move_2sd"] and rows["MX10Y"]["move_2sd"] and set(res["moves"]) == {"BRL", "MX10Y"}
    assert rows["BRL"]["month_return_pct"] == 9.0 and rows["BRL"]["real_carry"] == round(13.75 - 4.5 + 0.12, 3)
    assert rows["MX10Y"]["real_carry"] == round(9.4 - 3.5, 3)
    # FR-DE has no October composite: shown at its latest month, unranked, counted as stale
    assert rows["FR-DE"]["stale"] and rows["FR-DE"]["data_month"] == "2026-09" and rows["FR-DE"]["rank_composite"] is None
    assert res["stale"] == ["FR-DE"] and rows["DE10Y"]["n_ranked"] == 3
    assert rows["FR-DE"]["rating_reviews"] == "2026-11-27 S&P review" and rows["FR-DE"]["next_election"] == ""
    assert rows["DE10Y"]["real_carry"] == rows["DE10Y"]["carry"] or rows["DE10Y"]["real_carry"] is None
    md = screener.report_markdown(res)
    assert "| Mexico | MX10Y |" in md and "FR-DE*" in md and "BRL, MX10Y" in md and "2026-11-27 S&P review" in md


def test_screener_outputs_are_filed_as_a_report(tmp_path):
    inp = _toy_inputs()
    res = screener.compute(inp, [], [], REGISTRY, [], date(2026, 11, 4))
    files = screener.write_outputs(res, tmp_path)
    assert files == ["results/screener/latest.json", "results/screener/screener_2026-10.csv",
                     "data/ledger/reports/2026-11-04_screener-2026-10.md"]
    text = (tmp_path / files[2]).read_text()
    meta, body = __import__("ledger.build", fromlist=["parse_front_matter"]).parse_front_matter(text)
    assert meta["type"] == "screener" and meta["date"] == "2026-11-04" and body.startswith("# Screener after the 2026-10 rebalance")
    assert len(_rows(tmp_path / files[1])) == 8 and json.loads((tmp_path / files[0]).read_text())["as_of"] == "2026-10"


# ----------------------------------------------------------------------------- to-do page
from ledger import build  # noqa: E402


def test_todo_parsing_and_build(tmp_path):
    td = build.parse_todo("# To do\n\nIntro line.\n\n## A\n\n- [x] done thing (with a longer note here)\n- [ ] open thing\n\n## B\n\n- [ ] other\n")
    assert td["n"] == 3 and td["done"] == 1 and td["intro"] == "Intro line."
    assert td["sections"][0]["items"][0] == {"done": True, "text": "done thing", "note": "with a longer note here"}
    assert td["sections"][1] == {"title": "B", "items": [{"done": False, "text": "other", "note": None}], "done": 0, "n": 1}
    real = build.build_todo()
    titles = [s["title"] for s in real["sections"]]
    assert titles == ["Technical", "Automation", "Algorithm"]
    auto = {i["text"]: i["done"] for i in real["sections"][1]["items"]}
    assert auto["Resolving decisions and forecasts"] and auto["Marking open positions"] and auto["Risk Manager"] and auto["Screener"]
    assert not auto["Anthropic API key"]
    out = tmp_path / "app"
    build.build(out, today=date(2026, 11, 4))
    for name in ("todo", "marks", "screener"):
        assert (out / f"data/{name}.json").exists()
    dec = json.loads((out / "data/decisions.json").read_text())
    d1 = next(d for d in dec["items"] if d["id"] == "D001")
    # FR-DE is marked daily from the Riksbank since 2026-11-06 (it was a monthly ECB IRS average before)
    assert d1["mark_instrument"] == "FR-DE" and d1["mark_frequency"] == "daily" and d1["position_type"] == "continuous"
    assert d1["mark"] > 120 and d1["mark_can_act"]
    fc = json.loads((out / "data/forecasts.json").read_text())
    assert all(f["resolution_source"] == "AP race call" for f in fc["items"][:5])


def test_marks_watchdog_flags_marks_older_than_two_days(tmp_path):
    from datetime import datetime, timezone
    from ledger import watchdog
    p = tmp_path / "marks.csv"
    marks.write_marks([{**_mark("BRL", "2026-11-03", 5.4), "fetched_at": "2026-11-04T10:10:03+00:00"}], p)
    old = watchdog.check(datetime(2026, 11, 6, 12, tzinfo=timezone.utc), 2, p)
    assert old["stale"] and old["age_days"] > 2 and old["title"] == "[ALERT] Ledger marks stale"
    new = watchdog.check(datetime(2026, 11, 5, 9, tzinfo=timezone.utc), 2, p)
    assert not new["stale"]
    assert watchdog.check(datetime(2026, 11, 5, tzinfo=timezone.utc), 2, tmp_path / "none.csv")["stale"]


def test_daily_workflow_stages_only_existing_paths_and_fails_loudly():
    wf = (ROOT / ".github/workflows/ledger-daily.yml").read_text()
    step = wf[wf.index("- name: Commit and push"):wf.index("- name: Open or update [RESOLVE?] issues")]
    assert "2>/dev/null || true" not in step and '[ -e "$p" ]' in step and "push failed" in step
    assert "ledger.watchdog" in wf and (ROOT / ".github/workflows/ledger-watchdog.yml").exists()
