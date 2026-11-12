"""Config change C13 (approved by Ethan 2026-11-12): a C08 book has no position-count cap (it holds every watchlist
instrument), and the 2% per-position cap and the 3-10% total band still apply. The count tests fail before C13 (the
summary and context reported a cap of 8 for a book of 10); the per-position tests hold C08's 2% cap in every case."""
from datetime import date

import pytest

from ledger import janus as J
from test_janus_c08 import WL, book, c08, day_marks, marks, run


@pytest.fixture(autouse=True)
def no_store(tmp_path, monkeypatch):
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path / "no-store"))


def risks(path):
    return {i: p["open"]["risk_pct"] for i, p in book(path).items()}


def test_the_c08_book_never_puts_more_than_2_percent_on_one_position(tmp_path):
    # extreme forecasts on two instruments, near-even on the rest: both capped at exactly 2%
    probs = {i: (51 if k % 2 else 49) for k, i in enumerate(WL)} | {"US10Y": 99, "JPY": 1}
    assert run(tmp_path, c08(probs=probs))["ok"]
    r = risks(tmp_path / "r.jsonl")
    assert r["US10Y"] == pytest.approx(J.MAX_RISK_POS) and r["JPY"] == pytest.approx(J.MAX_RISK_POS)
    assert max(r.values()) <= J.MAX_RISK_POS + 1e-9
    assert J.RISK_BUDGET[0] - 1e-6 <= sum(r.values()) <= J.RISK_BUDGET[1] + 1e-6


def test_the_cap_holds_when_the_total_is_scaled_down_into_the_band(tmp_path):
    # every forecast at 99 or 1: 10 x 4.9% raw, each capped at 2% (20%), then scaled to the 10% ceiling
    assert run(tmp_path, c08(probs={i: (99 if k % 2 else 1) for k, i in enumerate(WL)}))["ok"]
    r = risks(tmp_path / "r.jsonl")
    assert len(r) == 10 and all(v == pytest.approx(1.0) for v in r.values())
    assert sum(r.values()) == pytest.approx(J.RISK_BUDGET[1])


def test_the_cap_binds_before_the_band_when_a_data_failure_leaves_one_instrument(tmp_path):
    """Nine marks failed and named: the one instrument left would need 3% to reach the band, but stays at 2%."""
    others = [i for i in WL if i != "US10Y"]
    mk = [m for m in marks("2026-11-10") if m["instrument"] not in others] + \
        [m for m in marks("2026-11-04") if m["instrument"] in others]
    df = [{"instrument": i, "mark": "daily mark (named failure)", "last_mark": "2026-11-04"} for i in others]
    res = run(tmp_path, c08(data_failure=df), mk=mk)
    assert res["ok"], res["errors"]
    r = risks(tmp_path / "r.jsonl")
    assert r == {"US10Y": pytest.approx(J.MAX_RISK_POS)}


def test_the_fill_never_raises_the_risk_above_the_order(tmp_path):
    path = tmp_path / "r.jsonl"
    probs = {i: (51 if k % 2 else 49) for k, i in enumerate(WL)} | {"US10Y": 99}
    assert run(tmp_path, c08(probs=probs))["ok"]
    J.process(J.load(path), day_marks("2026-11-12"), date(2026, 11, 13), path)
    for p in book(path).values():
        assert p["status"] == "open" and p["fill"]["risk_pct"] <= min(p["open"]["risk_pct"], J.MAX_RISK_POS) + 1e-4


def test_a_c08_book_has_no_position_count_cap(tmp_path):
    path = tmp_path / "r.jsonl"
    assert J.max_open_for([]) == J.MAX_OPEN == 8                           # before any C08 review: the old cap
    assert run(tmp_path, c08())["ok"]
    recs = J.load(path)
    assert len(book(path)) == 10 > J.MAX_OPEN                               # every watchlist instrument
    assert J.max_open_for(recs) is None
    s = J.summarize(recs, marks("2026-11-10"), date(2026, 11, 12))
    assert s["max_open"] is None and s["n_open"] == 10
    # a failed C08 review does not lift the cap
    failed = [{"type": "run", "session": "daily_review", "c08": True, "status": "failed"}]
    assert J.max_open_for(failed) == J.MAX_OPEN


def test_c13_is_recorded():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    doc = (root / "docs/config_changes.md").read_text(encoding="utf-8")
    assert "| C13 | 2026-11-12 |" in doc and "## C13" in doc and "Approved by Ethan on 2026-11-12" in doc
    assert "C13" in (root / "docs/janus/daily_review.md").read_text(encoding="utf-8")
    assert J.C13_FROM == date(2026, 11, 12)
