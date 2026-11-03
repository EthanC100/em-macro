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
    assert home["account_value"] is not None and len(home["positions"]) >= 1
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
    assert len(alg["positions"]) == 14 and {s["sleeve"] for s in alg["by_sleeve"]} == {"Bonds", "Currencies"}
    tr = json.loads((out / "data/trials.json").read_text())
    assert tr["summary"]["n"] >= 12 and next(t for t in tr["items"] if t["trial_id"] == "T01")["status"] == "pass"
    assert next(t for t in tr["items"] if t["trial_id"] == "T12")["status"] == "fail"
    el = json.loads((out / "data/elections.json").read_text())
    assert el["n_past"] > 100 and any(s["kind"] == "odds" for s in el["signals"])
    rp = json.loads((out / "data/reports.json").read_text())
    assert any(r["source"] == "results/T01_ts_trend.md" for r in rp["items"])
    for r in rp["items"]:
        assert (out / r["file"]).exists()


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

### Country (optional)

Euro area
"""


def test_forecast_intake_and_resolution(ledger_root):
    res = intake.process("forecast", FORECAST_BODY, 50, TODAY, ledger_root)
    assert res["ok"] and res["id"] == "F006"
    row = _rows(ledger_root / "data/ledger/forecasts.csv")[-1]
    assert row["my_prob"] == "70" and row["claude_prob"] == "" and row["country"] == "Euro area"
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
