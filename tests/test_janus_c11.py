"""Config change C11 (approved by Ethan 2026-11-11, before C08's first review): a C08 review's forecast base marks,
resolution windows and the fills of its orders, resizes and closes use the first first-hand daily mark dated
strictly after the review's UTC date, rolling forward over weekends and holidays: never a close the review could
already see. Every rule test here fails before C11 and passes after; one guard checks that orders from before
C08 keep their rule."""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from ledger import janus as J
from test_janus import _m
from test_janus_c08 import (LEVELS, SR, T, UNITS, WL, _chain_until, _runbook_example, _write, book, c08, day_marks,
                            marks, run)

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


@pytest.fixture(autouse=True)
def no_store(tmp_path, monkeypatch):
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path / "no-store"))


def forecast_base(tmp_path, now, mk, name="r.jsonl"):
    path = tmp_path / name
    assert run(tmp_path, c08(now=now), now=now, mk=marks((now - timedelta(days=1)).date().isoformat()), name=name)["ok"]
    f = next(r for r in J.load(path) if r["type"] == "forecast" and r["instrument"] == "US10Y")
    return J.forecast_outcome(f, mk, date(2027, 1, 31))


def test_the_base_mark_is_never_the_review_days_own_close(tmp_path):
    mk = day_marks("2026-11-11") + day_marks("2026-11-12", -0.02)
    out = forecast_base(tmp_path, T, mk)                                    # Wednesday 11 Nov, 23:07 UTC
    assert (out["base_date"], out["base_value"]) == ("2026-11-12", pytest.approx(LEVELS["US10Y"] - 0.02))
    assert out["target_date"] == "2026-12-10"                               # 20 weekdays after the base mark


def test_a_friday_review_rolls_to_monday_and_a_holiday_to_the_next_session(tmp_path):
    fri = datetime(2026, 11, 13, 23, 7, tzinfo=UTC)
    out = forecast_base(tmp_path, fri, day_marks("2026-11-13") + day_marks("2026-11-16"), name="fri.jsonl")
    assert out["base_date"] == "2026-11-16"
    # no US10Y mark on Thursday 12 Nov (a market holiday, say): the next session's mark, Friday's
    mk = [m for m in day_marks("2026-11-12") if m["instrument"] != "US10Y"] + day_marks("2026-11-13")
    out = forecast_base(tmp_path, T, day_marks("2026-11-11") + mk, name="hol.jsonl")
    assert out["base_date"] == "2026-11-13"


def test_orders_fill_and_closes_happen_only_after_the_review_day(tmp_path):
    recs = _chain_until(245)                                  # J001 (US10Y) and J002 (GB10Y) before C08
    path = tmp_path / "r.jsonl"
    _write(path, recs)
    J.process(J.load(path), marks("2026-11-10"), date(2026, 11, 11), path)       # J001, J002 fill at 10 Nov
    assert J.apply_proposal(c08(), now=T, path=path, marks_rows=marks("2026-11-10"))["ok"]
    J.process(J.load(path), marks("2026-11-10") + day_marks("2026-11-11"), date(2026, 11, 12), path)
    st = J.positions(J.load(path))
    assert st["J001"]["status"] == "open" and all(p["status"] == "pending" for p in book(path).values())
    J.process(J.load(path), marks("2026-11-10") + day_marks("2026-11-11") + day_marks("2026-11-12"),
              date(2026, 11, 13), path)
    st = J.positions(J.load(path))
    assert st["J001"]["close"]["date"] == st["J002"]["close"]["date"] == "2026-11-12"
    assert {p["fill"]["entry_date"] for p in book(path).values()} == {"2026-11-12"}
    assert all("strictly after" in p["open"]["entry_rule"] for p in book(path).values())


def test_a_resize_fills_after_the_review_day_too(tmp_path):
    path = tmp_path / "r.jsonl"
    run(tmp_path, c08())
    J.process(J.load(path), day_marks("2026-11-12"), date(2026, 11, 13), path)
    t2 = T + timedelta(days=1)
    assert run(tmp_path, c08(now=t2, probs={"JP10Y": 40}), now=t2, mk=day_marks("2026-11-12"))["ok"]
    J.process(J.load(path), day_marks("2026-11-12", 0.01), date(2026, 11, 13), path)      # the review day's mark only
    assert book(path)["JP10Y"]["status"] == "pending"
    J.process(J.load(path), day_marks("2026-11-12") + day_marks("2026-11-13"), date(2026, 11, 14), path)
    assert book(path)["JP10Y"]["fill"]["entry_date"] == "2026-11-13"


def test_orders_not_from_a_c08_review_keep_on_or_after():
    """A guard, not a C11 rule (it passes before C11 too): records before C08 are not re-judged, so a pre-C08 order
    still fills at a mark dated on its decision date."""
    recs = []
    J.append(recs, {"type": "open", "position_id": "J001", "instrument": "US10Y", "direction": "long", "risk_pct": 1.0,
                    "stop": 5.10, "horizon": "2026-12-18", "probability": 60, "decision_date": "2026-11-09"}, None)
    J.process(recs, [_m("US10Y", "2026-11-09", 4.92)], date(2026, 11, 10), None)
    assert J.positions(recs)["J001"]["fill"]["entry_date"] == "2026-11-09"


def test_the_dry_run_and_the_runbook_example_show_marks_after(tmp_path):
    ex = _runbook_example()
    ex.pop("data_failure")
    ex.update(sources_read=SR, model="claude-opus-5-5")
    ex["time_anchor"]["now_utc"] = "2026-11-11T23:07:00Z"
    for f in ex["forecasts"]:
        if f["reasoning"] == "...":
            f["reasoning"] = "The latest data and positioning lean this way."
        if f["opposition"]["case_against"] == "...":
            f["opposition"]["case_against"] = "It is priced, and the trend could turn."
    path = tmp_path / "r.jsonl"
    _write(path, _chain_until(245))
    res = J.apply_proposal(ex, now=T, path=path, marks_rows=marks("2026-11-10"), dry_run=True)
    rb = (ROOT / "docs/janus/daily_review.md").read_text(encoding="utf-8")
    shown = rb.split("example above, run at 23:07 UTC", 1)[1].split("```json\n", 1)[1].split("\n```", 1)[0]
    shown = json.loads(shown.replace(', "..."]', "]"))
    assert res["ok"] and res["marks_after"] == shown["marks_after"] == "2026-11-11"
    assert (res["risk_after_pct"], res["would_close"], res["would_hold"]) == \
        (shown["risk_after_pct"], shown["would_close"], shown["would_hold"])
    assert [list(x) for x in res["would_open"][:2]] == shown["would_open"]


def test_c11_is_recorded():
    assert J.C11_FROM == date(2026, 11, 11)
    doc = (ROOT / "docs/config_changes.md").read_text(encoding="utf-8")
    assert "| C11 | 2026-11-11 |" in doc and "## C11" in doc and "Approved by Ethan on 2026-11-11" in doc
    assert "strictly after" in (ROOT / "janus/watchlist.yaml").read_text(encoding="utf-8")
    assert "strictly after the forecast's date" in (ROOT / "docs/fund/allocation.md").read_text(encoding="utf-8")
