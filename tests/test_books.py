"""Books, audit seals, what-changed and stress tests (ledger/books.py, audit.py, changes.py, stress.py)."""
import json
import shutil
from datetime import date

import pytest

from ledger import audit, books, build, changes, pricing as PX, stress

TODAY = date(2026, 11, 6)


@pytest.fixture(scope="module")
def bk():
    return books.build_books(TODAY, build.build_algorithm())


def test_three_books_with_colours_and_live_starts(bk):
    assert [bk[b]["color"] for b in ("me", "algorithm", "janus")] == ["blue", "gold", "purple"]
    assert bk["me"]["live_start"] == "2026-10-30"
    assert "not AI" in bk["algorithm"]["kind"]
    v10, v11 = bk["algorithm"]["versions"]
    assert v10["is_live"] and not v11["is_live"] and v11["mtd_pct"] is None   # v1.1 is pre-live until Dec 2026
    assert v10["estimate"]["label"] == "estimate, month to date"
    assert v10["series"][0][1] == 100.0 and v10["series"][-1][2] == "estimate"


def test_monthly_only_instruments_are_carried_and_flagged(bk):
    est = bk["algorithm"]["versions"][1]["estimate"]
    flagged = set(est["carried"])
    for p in est["positions"]:
        if p["instrument"] in ("ID10Y", "CO10Y", "CL10Y", "IT-DE"):
            assert p["instrument"] in flagged


def test_exposures_flag_shared_country_and_never_include_forecasts(bk):
    ex = bk["exposures"]
    assert all(i["book"] in ("me", "algorithm v1.0", "algorithm v1.1", "janus") for i in ex["items"])
    for row in ex["by_country"]:
        owners = {b.split(" ")[0] for b in row["books"]}
        assert row["shared"] == (len(owners) > 1)


def test_signal_attribution_splits_by_aligned_z():
    per = [{"mtd_pct": 1.0, "size_pct": 10, "carry_z": 1.0, "trend_z": 1.0, "value_z": -1.0}]
    att = {a["key"]: a["pnl_pct"] for a in books.signal_attribution(per)}
    assert att == {"carry": 0.5, "trend": 0.5, "value": 0.0}


def test_audit_seals_detect_an_edited_decision(tmp_path, monkeypatch):
    root = tmp_path
    (root / "data/ledger").mkdir(parents=True)
    for f in ("decisions.csv", "forecasts.csv"):
        shutil.copy(audit.ROOT / "data/ledger" / f, root / "data/ledger" / f)
    monkeypatch.setattr(audit, "ROOT", root)
    seals = root / "data/ledger/seals.jsonl"
    assert audit.seal(seals, now="2026-11-06T00:00:00+00:00")
    assert audit.verify_seals(seals)["ok"]
    p = root / "data/ledger/decisions.csv"
    p.write_text(p.read_text().replace("Exit if the OAT-Bund spread tightens to 115bp", "Exit at 100bp"))
    v = audit.verify_seals(seals)
    assert not v["ok"] and "D001" in v["error"]


def test_changes_lists_pnl_trades_and_resolved_forecasts():
    prev = {"index": {"me": 100.0, "janus": 100.0}, "algo_effective": {"v1.0": "2026-11"},
            "decisions": {}, "forecasts": {"F001": {"status": "open"}}, "janus": {}, "janus_no_trades": 0}
    cur = {"index": {"me": 99.8, "janus": 100.0}, "algo_effective": {"v1.0": "2026-12"},
           "decisions": {"D003": {"status": "open", "action": "Buy", "instrument": "USD/BRL"}},
           "forecasts": {"F001": {"status": "resolved", "outcome": "yes"}},
           "janus": {"J001": {"status": "pending", "instrument": "WTI", "direction": "long"}}, "janus_no_trades": 0}
    kinds = [i["kind"] for i in changes.diff(prev, cur)]
    assert kinds.count("pnl") == 1 and kinds.count("trade") == 3 and "forecast" in kinds
    assert changes.diff(None, cur)[0]["kind"] == "baseline"


def test_stress_replay_uses_cached_history_and_lists_missing(bk):
    cache = {"TRY|gfc": {"v0": 1.0, "v1": 1.25, "d0": "2008-08-29", "d1": "2008-10-31", "source": "t"}}
    res = stress.run(bk, cache)
    gfc = res["scenarios"][0]
    try_row = next(r for r in gfc["positions"] if r["instrument"] == "TRY" and r["book"] == "algorithm v1.0")
    assert try_row["pnl_pct"] == pytest.approx(0.9578 * (1 / 1.25 - 1) * 100, abs=0.01)
    assert any(m["instrument"] == "MX10Y" for m in gfc["missing"])


def test_pricing_conventions():
    assert PX.ret_long("fx_per_usd", 50, 40) == pytest.approx(0.25)         # local currency appreciates
    assert PX.ret_long("usd_per_fx", 1.0, 1.1) == pytest.approx(0.1)
    assert PX.ret_long("yield", 4.0, 5.0) == pytest.approx(-PX.duration_10y(4.0) / 100)
    assert PX.stop_hit("spread", "short", 159, 115, 110) and not PX.stop_hit("spread", "short", 159, 115, 150)
