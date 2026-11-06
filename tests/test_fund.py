"""The Horizons fund (ledger/fund.py): risk-weighted combination of the books, read only."""
import copy
import math
from datetime import date, timedelta

import pytest

from ledger import fund as F


def _series(start, end, daily):
    out, v, d = [], 100.0, start
    while d <= end:
        if d.weekday() < 5:
            out.append([d.isoformat(), round(v, 6)])
            v *= 1 + daily(d)
        d += timedelta(days=1)
    return out


def books(v11=None, janus=None, me=None, closed=None, v11_start="2026-11-30", janus_start="2026-11-06"):
    v11 = v11 if v11 is not None else _series(date(2026, 11, 30), date(2027, 9, 30), lambda d: 0.001 if d.day % 2 else -0.0008)
    janus = janus if janus is not None else _series(date(2026, 11, 6), date(2027, 9, 30), lambda d: 0.004 if d.day % 3 else -0.005)
    me = me if me is not None else _series(date(2026, 10, 30), date(2027, 9, 30), lambda d: 0.0)
    return {"algorithm": {"versions": [{"id": "v1.0", "series": [], "live_start": "2026-10-31", "is_live": True},
                                       {"id": "v1.1", "series": [p + ["official"] for p in v11], "live_start": v11_start,
                                        "is_live": True}]},
            "janus": {"series": janus, "live_start": janus_start, "summary": {"closed": closed or []}},
            "me": {"series": me, "live_start": "2026-10-30"}}


def test_not_started_before_every_member_is_live():
    b = books(v11=[])
    b["algorithm"]["versions"][1]["is_live"] = False
    f = F.build_fund(b, date(2026, 11, 6))
    assert not f["live"] and "algorithm v1.1" in f["status"] and f["series"] == []
    assert f["allocation"]["weights"] == {"algorithm v1.1": 0.9, "janus": 0.1}


def test_capital_shares_until_six_months_then_risk_weights():
    b = books()
    f = F.build_fund(b, date(2027, 2, 10))
    assert f["live"] and f["live_start"] == "2026-11-30" and f["series"][0] == ["2026-11-30", 100.0]
    assert f["allocation"]["weights"] == {"algorithm v1.1": 0.9, "janus": 0.1}
    assert f["allocation"]["basis"].startswith("capital shares")
    f = F.build_fund(b, date(2027, 9, 15))
    a = f["allocation"]
    assert a["basis"].startswith("risk")
    va, vj = a["vol"]["algorithm v1.1"]["ann_vol_pct"], a["vol"]["janus"]["ann_vol_pct"]
    want = (0.9 / va) / (0.9 / va + 0.1 / vj)
    assert a["weights"]["algorithm v1.1"] == pytest.approx(want, abs=1e-6)
    assert sum(a["weights"].values()) == pytest.approx(1.0)


def test_fund_return_is_the_weighted_sum_and_books_are_untouched():
    b = books()
    before = copy.deepcopy(b)
    f = F.build_fund(b, date(2026, 12, 31))
    assert b == before                                              # never written back into a book
    v11, jn = b["algorithm"]["versions"][1]["series"], b["janus"]["series"]
    idx = 100.0
    days = F.bdays(date(2026, 11, 30), date(2026, 12, 31))
    for d0, d1 in zip(days, days[1:]):
        ra = F.level_on(v11, d1) / F.level_on(v11, d0) - 1
        rj = F.level_on(jn, d1) / F.level_on(jn, d0) - 1
        idx *= 1 + 0.9 * ra + 0.1 * rj
    assert f["series"][-1][1] == pytest.approx(idx, abs=1e-3)


def _call(net, outcome, p=70, mp=50, d="2027-01-15"):
    return {"probability": p, "market_probability": mp, "close": {"date": d, "outcome": outcome, "net_pnl_pct": net}}


def test_janus_share_rule():
    s = F.janus_share([], _series(date(2026, 11, 6), date(2027, 1, 30), lambda d: 0.0), date(2027, 1, 31))
    assert s["share"] == 0.10
    good = [_call(0.3, "right") for _ in range(25)] + [_call(-0.2, "wrong") for _ in range(5)]
    s = F.janus_share(good, _series(date(2026, 11, 6), date(2027, 1, 30), lambda d: 0.0), date(2027, 1, 31))
    assert s["share"] == 0.20 and s["brier_janus"] < s["brier_market"]
    assert F.janus_share(good[:29], [], date(2027, 1, 31))["share"] == 0.10            # fewer than 30 calls
    no_mkt = [{**c, "market_probability": None} for c in good]
    assert F.janus_share(no_mkt, [], date(2027, 1, 31))["share"] == 0.10               # same calls only
    losing = [_call(-0.1, "right") for _ in range(30)]
    assert F.janus_share(losing, [], date(2027, 1, 31))["share"] == 0.10               # net P&L must be positive
    worse = [_call(0.1, "wrong", p=90, mp=50) for _ in range(30)]
    assert F.janus_share(worse, [], date(2027, 1, 31))["share"] == 0.10                # Brier must beat the market
    dd = _series(date(2026, 11, 6), date(2026, 12, 31), lambda d: -0.004)
    s = F.janus_share(good, dd, date(2026, 12, 31))
    assert s["share"] == 0.05 and s["drawdown_pct"] > 10


def test_correlation_needs_six_common_months():
    f = F.build_fund(books(), date(2027, 3, 15))
    assert not f["correlation"]["enough"]
    f = F.build_fund(books(), date(2027, 9, 15))
    pair = next(p for p in f["correlation"]["pairs"] if p["a"] == "algorithm v1.1" and p["b"] == "janus")
    assert pair["months"] >= 6 and pair["corr"] is not None and -1 <= pair["corr"] <= 1


def test_drawdown():
    s = [["2026-11-02", 100], ["2026-11-03", 110], ["2026-11-04", 95.7]]
    assert F.drawdown_pct(s, date(2026, 11, 4)) == pytest.approx(13.0)


def test_rule_is_documented_and_logged():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    doc = (root / "docs/fund/allocation.md").read_text()
    assert "90%" in doc and "10%" in doc and "20%" in doc and "5%" in doc and "30 resolved calls" in doc
    assert "| C04 |" in (root / "docs/config_changes.md").read_text()
    assert F.SHARES == {"algorithm v1.1": 0.90, "janus": 0.10} and F.MIN_RESOLVED_CALLS == 30
    assert (F.JANUS_UP, F.JANUS_DOWN, F.DRAWDOWN_LIMIT_PCT, F.MIN_MONTHS_FOR_VOL) == (0.20, 0.05, 10.0, 6)
