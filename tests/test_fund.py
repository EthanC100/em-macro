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
    assert f["allocation"]["weights"] == {"algorithm v1.1": 0.8, "janus": 0.2}


def test_capital_shares_until_six_months_then_risk_weights():
    b = books()
    f = F.build_fund(b, date(2027, 2, 10))
    assert f["live"] and f["live_start"] == "2026-11-30" and f["series"][0] == ["2026-11-30", 100.0]
    assert f["allocation"]["weights"] == {"algorithm v1.1": 0.8, "janus": 0.2}
    assert f["allocation"]["basis"].startswith("capital shares")
    f = F.build_fund(b, date(2027, 9, 15))
    a = f["allocation"]
    assert a["basis"].startswith("risk")
    va, vj = a["vol"]["algorithm v1.1"]["ann_vol_pct"], a["vol"]["janus"]["ann_vol_pct"]
    want = (0.8 / va) / (0.8 / va + 0.2 / vj)
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
        idx *= 1 + 0.8 * ra + 0.2 * rj
    assert f["series"][-1][1] == pytest.approx(idx, abs=1e-3)


def _call(net, outcome, p=70, mp=50, d="2027-01-15"):
    return {"probability": p, "market_probability": mp, "close": {"date": d, "outcome": outcome, "net_pnl_pct": net}}


FLAT = _series(date(2026, 11, 6), date(2027, 1, 30), lambda d: 0.0)
UPTO = date(2027, 1, 31)


def test_janus_starts_at_20_until_30_resolved_calls():
    s = F.janus_share([], FLAT, UPTO)
    assert s["share"] == 0.20 and "0 of 30" in s["reason"]
    good = [_call(0.3, "right") for _ in range(25)] + [_call(-0.2, "wrong") for _ in range(5)]
    assert F.janus_share(good[:29], [], UPTO)["share"] == 0.20                        # 29 calls: still 20%
    bad = [_call(-0.3, "wrong", p=90) for _ in range(29)]
    assert F.janus_share(bad, [], UPTO)["share"] == 0.20                              # even if losing, before 30
    no_mkt = [{**c, "market_probability": None} for c in good]
    assert F.janus_share(no_mkt, [], UPTO)["share"] == 0.20                           # counted on the same calls only


def test_janus_30_with_positive_pnl_and_better_brier():
    good = [_call(0.3, "right") for _ in range(25)] + [_call(-0.2, "wrong") for _ in range(5)]
    s = F.janus_share(good, FLAT, UPTO)
    assert s["share"] == 0.30 and s["net_pnl_pct_on_those_calls"] > 0 and s["brier_janus"] < s["brier_market"]
    late = good[:29] + [_call(0.3, "right", d="2027-02-10")]                         # resolved after the month end
    assert F.janus_share(late, [], UPTO)["share"] == 0.20


def test_janus_10_with_negative_pnl_or_worse_brier():
    losing = [_call(-0.1, "right") for _ in range(30)]                                # better Brier, P&L < 0
    s = F.janus_share(losing, [], UPTO)
    assert s["share"] == 0.10 and "negative P&L" in s["reason"]
    worse = [_call(0.1, "wrong", p=90, mp=50) for _ in range(30)]                     # P&L > 0, Brier worse
    s = F.janus_share(worse, [], UPTO)
    assert s["share"] == 0.10 and "worse Brier" in s["reason"]
    both = [_call(-0.1, "wrong", p=90, mp=50) for _ in range(30)]
    assert F.janus_share(both, [], UPTO)["share"] == 0.10


def test_janus_exact_tie_stays_at_20():
    flat_pnl = [_call(0.0, "right") for _ in range(30)]                               # P&L 0, Brier better
    assert F.janus_share(flat_pnl, [], UPTO)["share"] == 0.20
    same_brier = [_call(0.2, "right", p=60, mp=60) for _ in range(30)]               # P&L > 0, Brier equal
    s = F.janus_share(same_brier, [], UPTO)
    assert s["share"] == 0.20 and s["brier_janus"] == s["brier_market"] and "tie" in s["reason"]
    worse_tie = [_call(0.0, "wrong", p=90, mp=50) for _ in range(30)]                 # P&L 0 but Brier worse
    assert F.janus_share(worse_tie, [], UPTO)["share"] == 0.10


def test_drawdown_above_10_overrides_everything():
    dd = _series(date(2026, 11, 6), date(2026, 12, 31), lambda d: -0.004)
    good = [_call(0.3, "right", d="2026-12-15") for _ in range(30)]
    for calls in ([], good, [_call(-0.1, "right", d="2026-12-15") for _ in range(30)]):
        s = F.janus_share(calls, dd, date(2026, 12, 31))
        assert s["share"] == 0.05 and s["drawdown_pct"] > 10 and "overrides" in s["reason"]
    shallow = _series(date(2026, 11, 6), date(2026, 12, 31), lambda d: -0.002 if d.day < 20 else 0.0)
    assert 0 < F.drawdown_pct(shallow, date(2026, 12, 31)) <= 10
    assert F.janus_share(good, shallow, date(2026, 12, 31))["share"] == 0.30


def test_share_is_set_at_month_starts_in_the_fund():
    good = [_call(0.3, "right", d="2027-01-20") for _ in range(30)]
    f = F.build_fund(books(closed=good), date(2027, 3, 10))
    by_month = {h["from"]: h["janus_rule"]["share"] for h in f["history"]}
    assert by_month["2026-12-01"] == 0.20 and by_month["2027-01-01"] == 0.20
    assert by_month["2027-02-01"] == 0.30 and by_month["2027-03-01"] == 0.30        # calls closed in January
    assert f["history"][-1]["risk_shares"] == {"algorithm v1.1": 0.7, "janus": 0.3}


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
    assert "| Algorithm v1.1 (v1.0 + T18, mechanical) | 80% |" in doc and "| Janus (AI book) | 20% |" in doc
    assert "**30%**" in doc and "**10%**" in doc and "**5%**" in doc and "30 resolved calls" in doc
    assert "## Amendment, 2026-11-07" in doc
    cc = (root / "docs/config_changes.md").read_text()
    assert "| C04 |" in cc and "Amendment, 2026-11-07" in cc
    assert F.SHARES == {"algorithm v1.1": 0.80, "janus": 0.20} and F.MIN_RESOLVED_CALLS == 30
    assert (F.JANUS_START, F.JANUS_UP, F.JANUS_LOW, F.JANUS_DOWN) == (0.20, 0.30, 0.10, 0.05)
    assert (F.DRAWDOWN_LIMIT_PCT, F.MIN_MONTHS_FOR_VOL) == (10.0, 6)
    app = (root / "ledger/site/app.js").read_text()
    assert "starting risk share 80%) and Janus (20%)" in app and "risk share 90%" not in app
