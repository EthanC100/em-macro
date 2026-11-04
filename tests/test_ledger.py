"""Tests for the Ledger app build and issue intake (stdlib only, fast)."""
import csv
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from ledger import build, intake, schema, scoring

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 3)
FREEZE_MONTH = "2026-09"      # last month of the frozen v1.0 test
LIVE_START_MONTH = "2026-11"  # first live month (positions from the 3 Nov 2026 rebalance); 2026-10 is pre-live


def _live_results():
    """(number of current positions, number of live months) from the committed results, which
    the monthly workflow rewrites before running the tests."""
    with open(ROOT / "results/systematic/positions.csv", newline="") as f:
        n_pos = sum(1 for _ in csv.DictReader(f))
    with open(ROOT / "results/systematic/paper_pnl.csv", newline="") as f:
        n_live = sum(1 for r in csv.DictReader(f) if (r.get("month") or "") >= LIVE_START_MONTH)
    return n_pos, n_live


# ----------------------------------------------------------------------------- schema / scoring
def test_dates_and_numbers_parse():
    assert schema.parse_date("2027-04-18") == date(2027, 4, 18)
    assert schema.parse_date("18 April 2027") == date(2027, 4, 18)
    assert schema.parse_date("3 Nov 2026") == date(2026, 11, 3)
    assert schema.parse_date("not a date") is None
    assert schema.parse_number("tightens to 115bp") == 115.0
    assert schema.parse_number("closes above 5.70") == 5.7
    assert schema.parse_number("no level here") is None
    assert schema.parse_probability("65%") == 65.0
    assert schema.parse_probability("0.65") == 65.0
    assert schema.parse_probability("120") is None


def test_kelly_sizing():
    assert schema.kelly_size_pct(65) == 3.75      # 0.125 x (2 x 0.65 - 1)
    assert schema.kelly_size_pct(50) == 0.0
    assert schema.kelly_size_pct(40) == 0.0


def _decision(**over):
    d = dict(date="2026-11-03", country="Brazil", instrument="USD/BRL", action="Buy", size_pct="1.5",
             probability="60", horizon="2026-12-25", entry_trigger="5.40", stop="exit above 5.70",
             thesis="t", key_factors="k", change_mind="c", vs_consensus="v")
    d.update(over)
    return d


def test_validation_rules():
    assert schema.validate_decision(_decision())[0] == []
    errs, _ = schema.validate_decision(_decision(stop="exit if it goes badly"))
    assert any("numeric price or yield level" in e for e in errs)
    errs, _ = schema.validate_decision(_decision(size_pct="2.5"))
    assert any("at most 2%" in e for e in errs)
    errs, _ = schema.validate_decision(_decision(probability=""))
    assert any("Probability" in e for e in errs)
    errs, _ = schema.validate_decision(_decision(horizon="someday"))
    assert any("Horizon" in e for e in errs)
    errs, _ = schema.validate_decision(_decision(action="No trade", size_pct="0", stop="above 5.70"))
    assert errs == []
    errs, _ = schema.validate_decision(_decision(action="No trade", size_pct="1"))
    assert any("No trade" in e for e in errs)


def test_brier_and_pnl():
    assert scoring.brier("65", 1) == 0.1225
    assert scoring.brier("65", 0) == 0.4225
    # stop below entry: the position loses when the level falls; exit above entry is a gain
    assert scoring.decision_pnl_pct({"action": "Sell", "entry_level": "140", "stop": "115bp",
                                     "exit_price": "165", "size_pct": "1.0"}) == 1.0
    # stop above entry: exit below entry is a gain
    assert scoring.decision_pnl_pct({"action": "Buy", "entry_level": "5.40", "stop": "5.70",
                                     "exit_price": "5.10", "size_pct": "2"}) == 2.0
    # explicit P&L wins
    assert scoring.decision_pnl_pct({"action": "Buy", "pnl_pct": "-0.8"}) == -0.8
    # no entry level: not computable
    assert scoring.decision_pnl_pct({"action": "Buy", "stop": "5.70", "exit_price": "5.1", "size_pct": "1"}) is None
    c = scoring.cumulative([0.2, 0.1, None, 0.3])
    assert c["n"] == 3 and c["mean"] == 0.2 and c["running"] == [0.2, 0.15, None, 0.2]
    bins = scoring.calibration_bins([(45, 0), (55, 1), (65, 1)])
    assert bins[2] == {"bin": "40-59", "n": 2, "mean_forecast": 50.0, "observed": 50.0}


# ----------------------------------------------------------------------------- build
def test_build_writes_site_and_json(tmp_path):
    out = tmp_path / "app"
    info = build.build(out, today=TODAY)
    assert (out / "index.html").exists() and (out / "sw.js").exists() and (out / "manifest.webmanifest").exists()
    assert info["build"] in (out / "sw.js").read_text()
    man = json.loads((out / "data/manifest.json").read_text())
    assert "data/home.json" in man["files"] and "app.js" in man["files"]
    for f in man["files"]:
        assert (out / f).exists(), f
    home = json.loads((out / "data/home.json").read_text())
    assert home["account_index"] is not None and len(home["positions"]) >= 1
    assert home["account_index_label"] == "Account index (start = 100, live from Nov 2026)"
    assert home["account_base_month"] == "2026-10" and home["history_index_base_month"] == FREEZE_MONTH
    # the live index is 100 at the end of the last pre-live month and moves only with live months
    alg_ = json.loads((out / "data/algorithm.json").read_text())
    prod = 1.0
    for m in alg_["months"]:
        if m["live"]:
            prod *= 1 + m["net"]
    assert home["account_index"] == pytest.approx(100 * prod, abs=1e-3)
    assert home["account_change_pct"] == pytest.approx(home["account_index"] - 100, abs=1e-3)
    if (alg_["rebalance"]["effective_from"] or "") >= "2026-12":
        assert home["usd_switched"] and home["usd_capital"] == 10_000_000.0
        assert home["account_usd"] == pytest.approx(
            10_000_000.0 * home["account_index"] / home["index_at_switch"], abs=0.01)
    else:
        assert not home["usd_switched"] and home["usd_capital"] == 100_000.0 and home["usd_switch_note"] is None
        assert home["account_usd"] == pytest.approx(100_000.0 * home["account_index"] / 100, abs=0.01)
    by_m = {m["month"]: m for m in alg_["months"]}
    assert by_m["2026-10"]["account_index"] == 100.0 and by_m[FREEZE_MONTH]["account_index"] is None
    # history index figures unchanged: 100 at the end of the freeze month, October keeps its loss
    assert by_m[FREEZE_MONTH]["account_value"] == pytest.approx(100.0)
    assert by_m["2026-10"]["account_value"] == pytest.approx(100 * (1 + by_m["2026-10"]["net"]), abs=1e-3)
    assert all(m["account_value"] is None for m in alg_["months"] if m["live"])
    dec = json.loads((out / "data/decisions.json").read_text())
    ids = {d["id"] for d in dec["items"]}
    assert {"D001", "D002"} <= ids
    d1 = next(d for d in dec["items"] if d["id"] == "D001")
    assert d1["kelly_cap_pct"] == 3.75 and d1["stop_level"] == 115.0 and d1["horizon"] == "2027-04-18"
    fc = json.loads((out / "data/forecasts.json").read_text())
    assert fc["summary"]["n"] >= 5 and fc["items"][0]["my_prob"] == 45.0
    alg = json.loads((out / "data/algorithm.json").read_text())
    assert alg["backtest"]["months"] == 81
    assert abs(alg["backtest"]["ann_return_pct"] - 5.959) < 0.01
    assert alg["frozen"]["test_2020_on"]["sharpe"] == pytest.approx(0.6536, abs=1e-3)
    _, n_live = _live_results()
    assert build.LIVE_START_MONTH == LIVE_START_MONTH
    by_month = {m["month"]: m for m in alg["months"]}
    oct26 = by_month["2026-10"]
    assert oct26["phase"] == "pre_live" and oct26["pre_live"] and not oct26["live"]
    assert by_month[FREEZE_MONTH]["phase"] == "backtest"
    assert all(m["live"] == (m["month"] >= LIVE_START_MONTH) for m in alg["months"])
    assert alg["live"]["months"] == alg["rebalance"]["n_live_months"] == n_live
    assert alg["rebalance"]["pre_live_months"] == ["2026-10"] and alg["rebalance"]["live_start_month"] == "2026-11"
    n_pos, _ = _live_results()
    assert len(alg["positions"]) == n_pos and {s["sleeve"] for s in alg["by_sleeve"]} == {"Bonds", "Currencies"}
    tr = json.loads((out / "data/trials.json").read_text())
    assert tr["summary"]["n"] >= 12 and next(t for t in tr["items"] if t["trial_id"] == "T01")["status"] == "pass"
    assert next(t for t in tr["items"] if t["trial_id"] == "T12")["status"] == "fail"
    status = {t["trial_id"]: t["status"] for t in tr["items"]}
    assert status["T14"] == "inconclusive" and status["T15"] == "pending"      # election study and its live test
    # T01-T15, then the T16-T19 risk batch (T18 passed; T16, T17, T19 failed)
    assert tr["summary"]["n"] == 19 and tr["summary"]["inconclusive"] == 1 and tr["summary"]["pending"] == 1
    assert status["T18"] == "pass" and {status[t] for t in ("T16", "T17", "T19")} == {"fail"}
    # v1.1 (v1.0 + T18) next to v1.0 on the Algorithm page
    v11, sbs = alg["v11"], alg["side_by_side"]
    assert [v["id"] for v in sbs["versions"]] == ["v1.0", "v1.1"]
    assert v11["live_start_month"] == "2026-12" and sbs["common_window"]["start"] == "2026-12"
    assert all(m["live"] == (m["month"] >= "2026-12") for m in v11["months"])
    for v in sbs["versions"]:
        assert set(v["live"]) >= {"months_live", "live_pnl_pct", "sharpe", "max_drawdown_pct", "turnover_x_pa"}
    assert sbs["versions"][0]["live"]["months_live"] == n_live
    assert sbs["versions"][1]["live"]["months_live"] == sum(m["live"] for m in v11["months"])
    assert sbs["versions"][0]["backtest"]["sharpe"] == pytest.approx(0.6536, abs=1e-4)
    assert sbs["versions"][1]["backtest"]["sharpe"] == pytest.approx(0.9163, abs=1e-4)
    assert sbs["versions"][1]["backtest"]["turnover_x_pa"] == pytest.approx(11.5997, abs=1e-4)
    assert len(v11["positions"]) == sum(1 for _ in open(ROOT / "results/systematic_v1.1/positions.csv")) - 1
    el = json.loads((out / "data/elections.json").read_text())
    if (ROOT / "data/elections/calendar.csv").exists():
        # the election tracker's calendar takes precedence over the historical event files (README section 14)
        assert el["sources"][0] == "data/elections/calendar.csv"
        mx = next(c for c in el["upcoming"] if c.get("id") == "mx-2027-legislative")
        assert mx["event"] == "Mexico legislative, 6 Jun 2027"
        assert all(c["event"] for c in el["upcoming"])                 # no blank labels
        pl = next(c for c in el["upcoming"] if c.get("id") == "pl-2027-parliamentary")
        assert pl["event"] == "Poland legislative, by 11 Nov 2027"     # due_by: the date is a legal deadline
    else:
        assert el["n_past"] > 100 and any(s["kind"] == "odds" for s in el["signals"])
    rp = json.loads((out / "data/reports.json").read_text())
    assert any(r["source"] == "results/T01_ts_trend.md" for r in rp["items"])
    for r in rp["items"]:
        assert (out / r["file"]).exists()


def test_tracker_event_label():
    row = {"id": "mx-2027-legislative", "country": "Mexico", "type": "legislative", "status": "scheduled"}
    assert build.tracker_event_label(row, date(2027, 6, 6)) == "Mexico legislative, 6 Jun 2027"
    r2 = {"id": "cz-2028-presidential-r2", "country": "Czech Republic", "type": "presidential", "status": "scheduled"}
    assert build.tracker_event_label(r2, date(2028, 2, 14)) == "Czech Republic presidential run-off, 14 Feb 2028"
    due = {"id": "my-2028-general", "country": "Malaysia", "type": "legislative", "status": "due_by"}
    assert build.tracker_event_label(due, date(2028, 2, 17)) == "Malaysia legislative, by 17 Feb 2028"
    assert build.tracker_event_label({"country": "Peru"}, None) == "Peru election"


# ----------------------------------------------------------------------------- intake
DECISION_BODY = """### Date

2026-11-04

### Country

Mexico

### Instrument

MX10Y

### Action

Buy

### Size (% of account at risk)

1.5

### Probability my view is right

62

### Horizon (date)

2027-01-15

### Entry trigger

Buy at 9.20% yield

### Stop / exit if wrong

Exit if the 10y yield rises above 9.80

### Thesis

Banxico cuts faster than priced.

### Key factors

Inflation; Fed.

### What would change my mind

A hawkish turn.

### How this differs from market consensus

Market prices two cuts; I expect four.
"""


@pytest.fixture
def ledger_root(tmp_path):
    (tmp_path / "data").mkdir()
    shutil.copytree(ROOT / "data/ledger", tmp_path / "data/ledger")
    return tmp_path


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_parse_issue_body():
    f = intake.parse_issue_body("### Title\n\nHello\n\n### Date (optional)\n\n_No response_\n\n### Content\n\nline 1\nline 2\n")
    assert f == {"Title": "Hello", "Date (optional)": "", "Content": "line 1\nline 2"}
    assert intake.classify("[Decision] something", []) == "decision"
    assert intake.classify("anything", ["ledger", "ledger:report"]) == "report"
    assert intake.classify("hello", []) is None


def test_decision_intake_appends_and_rejects(ledger_root):
    res = intake.process("decision", DECISION_BODY, 42, TODAY, ledger_root)
    assert res["ok"] and res["id"] == "D003" and "Logged as **D003**" in res["comment"]
    rows = _rows(ledger_root / "data/ledger/decisions.csv")
    assert rows[-1]["id"] == "D003" and rows[-1]["issue"] == "42" and rows[-1]["status"] == "open"
    assert rows[-1]["stop"] == "Exit if the 10y yield rises above 9.80"
    assert list(rows[-1].keys()) == schema.DECISION_COLUMNS
    # rejected: no numeric stop and too much risk
    bad = DECISION_BODY.replace("Exit if the 10y yield rises above 9.80", "Exit if it feels wrong").replace("\n1.5\n", "\n3\n")
    res = intake.process("decision", bad, 43, TODAY, ledger_root)
    assert not res["ok"] and "numeric price or yield level" in res["comment"] and "at most 2%" in res["comment"]
    assert len(_rows(ledger_root / "data/ledger/decisions.csv")) == 3


FORECAST_BODY = """### Question

Does the ECB cut in December 2026?

### My probability

70%

### Market probability

55

### Market source

Polymarket, 3 Nov 2026

### Claude probability (optional)

_No response_

### Resolution date

2026-12-18

### Resolution source

ECB press release

### Country (optional)

Euro area
"""


def test_forecast_intake_and_resolution(ledger_root):
    res = intake.process("forecast", FORECAST_BODY, 50, TODAY, ledger_root)
    assert res["ok"] and res["id"] == "F006"
    row = _rows(ledger_root / "data/ledger/forecasts.csv")[-1]
    assert row["my_prob"] == "70" and row["claude_prob"] == "" and row["country"] == "Euro area"
    assert row["resolution_source"] == "ECB press release"
    # the resolution source is required
    res = intake.process("forecast", FORECAST_BODY.replace("ECB press release", "_No response_"), 51, TODAY, ledger_root)
    assert not res["ok"] and "Resolution source is required" in res["comment"]
    # bad date
    res = intake.process("forecast", FORECAST_BODY.replace("2026-12-18", "December"), 51, TODAY, ledger_root)
    assert not res["ok"] and "Resolution date" in res["comment"]
    # resolve it
    body = "### Decision or forecast id\n\nf006\n\n### Outcome\n\nYes (forecast)\n\n### Exit price or result\n\nCut 25bp\n\n### P&L, % of account (optional)\n\n_No response_\n\n### Note (optional)\n\n_No response_\n"
    res = intake.process("resolve", body, 52, date(2026, 12, 18), ledger_root)
    assert res["ok"] and "Brier: me **0.090**" in res["comment"] and "market 0.203" in res["comment"]
    row = _rows(ledger_root / "data/ledger/forecasts.csv")[-1]
    assert row["status"] == "resolved" and row["outcome"] == "yes" and row["resolved_date"] == "2026-12-18"
    # resolving twice is refused; wrong outcome kind is refused
    assert not intake.process("resolve", body, 53, TODAY, ledger_root)["ok"]
    bad = body.replace("f006", "F001").replace("Yes (forecast)", "Right (decision)")
    assert "yes, no or void" in intake.process("resolve", bad, 54, TODAY, ledger_root)["comment"]


def test_decision_resolution_scores_pnl(ledger_root):
    body = DECISION_BODY
    intake.process("decision", body, 60, TODAY, ledger_root)
    # add an entry level by hand (as the owner would in the CSV) to make P&L computable
    p = ledger_root / "data/ledger/decisions.csv"
    rows = _rows(p)
    rows[-1]["entry_level"] = "9.20"
    intake.write_rows(p, rows, schema.DECISION_COLUMNS)
    res = intake.process("resolve", "### Decision or forecast id\n\nD003\n\n### Outcome\n\nRight (decision)\n\n### Exit price or result\n\n8.90\n", 61, date(2027, 1, 10), ledger_root)
    assert res["ok"] and "Brier score: **0.144**" in res["comment"]
    # stop 9.80 is above entry 9.20, so a fall to 8.90 is a gain of 1.5 x 0.30 / 0.60 = 0.75%
    assert "P&L: **+0.75%**" in res["comment"]


def test_report_intake_writes_markdown(ledger_root):
    body = "### Title\n\nWeekly review, week 45\n\n### Type\n\nweekly review\n\n### Country\n\nGlobal\n\n### Date (optional)\n\n_No response_\n\n### Content\n\n# Week 45\n\nCarry held up.\n"
    res = intake.process("report", body, 70, TODAY, ledger_root)
    assert res["ok"] and res["files"] == ["data/ledger/reports/2026-11-03_weekly-review-week-45.md"]
    text = (ledger_root / res["files"][0]).read_text()
    assert text.startswith("---\ndate: 2026-11-03\ntitle: Weekly review, week 45\ntype: weekly review\ncountry: Global\nissue: 70\n---\n")
    assert "Carry held up." in text
    meta, rest = build.parse_front_matter(text)
    assert meta["type"] == "weekly review" and rest.strip().startswith("# Week 45")
    res = intake.process("report", body.replace("weekly review", "memo"), 71, TODAY, ledger_root)
    assert not res["ok"] and "Type must be one of" in res["comment"]


# ----------------------------------------------------------------------------- evidence
def test_scored_elections_count(tmp_path):
    missing = build.count_scored_elections(tmp_path / "signals.csv", TODAY)
    assert missing["scored"] == 0 and not missing["found"] and "not found" in missing["note"]
    p = tmp_path / "signals.csv"
    p.write_text("country,vote_date,surprise,outcome\nBrazil,2026-10-04,2.1,win\nMexico,2027-06-06,,\nPoland,2025-05-18,-1.3,loss\n")
    c = build.count_scored_elections(p, TODAY)
    assert c == {"scored": 2, "pending": 1, "rows": 3, "found": True, "note": f"{p.as_posix()}: 2 scored of 3 rows (by column 'outcome')."}
    p.write_text("country,vote_date\nBrazil,2026-10-04\nMexico,2027-06-06\n")
    assert build.count_scored_elections(p, TODAY)["scored"] == 1      # no score column: past votes count


def test_evidence_groups_and_status(tmp_path):
    out = tmp_path / "app"
    build.build(out, today=TODAY)
    ev = json.loads((out / "data/evidence.json").read_text())
    groups = {g["key"]: g["items"] for g in ev["groups"]}
    live = groups["live"][0]
    _, n_live = _live_results()
    assert [i["id"] for i in groups["live"]] == ["v1.0", "v1.1"]          # "Live and under test"
    v11 = groups["live"][1]
    assert v11["trial_id"] == "T18" and v11["under_test"] and v11["live_since"] == "2026-12-03"
    assert v11["backtest_sharpe"] == pytest.approx(0.9163, abs=1e-4) and "frozen control v1.0" in v11["reason"]
    assert live["trial_id"] == "T01" and live["months_needed"] == 55 and live["live_months"] == n_live
    assert live["backtest_sharpe"] == pytest.approx(0.654, abs=1e-3)
    rule = groups["prospective"][0]
    assert rule["id"] == "election-rule" and rule["threshold"] == 15 and "0 of 15" in rule["reason"]
    assert rule["trial_id"] == "T15" and len(groups["prospective"]) == 1     # T15 is the election rule, listed once
    # T01 is the live entry, not a passed trial; T18 passed and runs live as v1.1
    assert [t["id"] for t in groups["passed"]] == ["T18"] and groups["passed"][0]["live_as"] == "v1.1"
    failed = {t["id"]: t for t in groups["failed"]}
    assert "T12" in failed and failed["T12"]["reason"].startswith("rejected (failed pre-registered pass rule)")
    assert all(0 < len(t["reason"]) <= 160 for t in groups["failed"])
    assert ev["overall"].startswith(f"No validated discretionary edge yet; v1.0 live for {n_live} month"
                                    f"{'s' if n_live != 1 else ''}")
    assert "15 rejected" in ev["overall"]                 # 11, T13 (trial T02), and T16, T17, T19
    assert "v1.1 (v1.0 + T18, passed) live for" in ev["overall"]
    assert "1 idea under prospective test" in ev["overall"]   # T15, the election continuation rule
    assert "T13" in failed and "T14" not in failed and "T15" not in failed and "T18" not in failed
    home = json.loads((out / "data/home.json").read_text())
    assert home["evidence_status"] == ev["overall"]


def _live_months(nets: dict) -> list[dict]:
    """Synthetic months: 2026-10 is the live base (index 100), later months are live."""
    rows, idx = [{"month": "2026-10", "live": False, "account_index": 100.0}], 100.0
    for m, r in nets.items():
        idx *= 1 + r
        rows.append({"month": m, "live": True, "account_index": round(idx, 3)})
    return rows


def test_usd_value_before_switch():
    months = _live_months({"2026-11": 0.02})
    u = build.usd_account(months, "2026-11")
    assert not u["usd_switched"] and u["usd_switch_note"] is None
    assert u["account_usd"] == pytest.approx(100_000 * 102.0 / 100)


def test_usd_value_new_capital_enters_at_switch_index():
    # positions effective December 2026 published: November is booked, US$ starts at exactly 10,000,000
    months = _live_months({"2026-11": 0.02})
    u = build.usd_account(months, "2026-12")
    assert u["usd_switched"] and u["index_at_switch"] == pytest.approx(102.0) and u["usd_switch_month"] == "2026-11"
    assert u["account_usd"] == pytest.approx(10_000_000.0)
    assert u["usd_switch_note"] == "Paper capital raised to US$10,000,000 (configuration change, not performance)"
    # a month later the dollar figure moves with the index only; the note is gone
    months = _live_months({"2026-11": 0.02, "2026-12": -0.01})
    u = build.usd_account(months, "2027-01")
    assert u["index_at_switch"] == pytest.approx(102.0) and u["usd_switch_note"] is None
    assert u["account_usd"] == pytest.approx(10_000_000 * 0.99, abs=1)
