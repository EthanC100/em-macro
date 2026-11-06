"""Collateral interest (ledger/books.py): total return = excess return + 3-month T-bill interest on the full
account value. Display only: no book's excess series, recorded P&L or evaluation changes."""
import copy
import math
from datetime import date

import pytest

from ledger import books as B
from ledger import fund as F


def _mb(rate=4.0, start="2026-10-01", end="2027-12-31"):
    rows = [{"date": d.isoformat(), "instrument": "USDCASH", "value": f"{rate}", "unit": "% yield", "frequency": "daily",
             "source": "fred DTB3", "source_url": "", "fetched_at": "t", "note": ""}
            for d in B.bdays(date.fromisoformat(start), date.fromisoformat(end))]
    return B.MarkBook(rows)


def test_flat_book_earns_exactly_the_tbill():
    mb = _mb(4.0)
    ser = [[d.isoformat(), 100.0] for d in B.bdays(date(2026, 11, 2), date(2026, 12, 31))]
    tot = B.total_return(ser, mb)
    cash = B.cash_index(mb, date(2026, 11, 2), date(2026, 12, 31))
    assert tot[-1][1] == pytest.approx(cash[-1][1], abs=1e-3)       # same accrual as the existing cash line
    assert tot[-1][1] == pytest.approx(100 * math.prod(1 + 0.04 * (b - a).days / 365 for a, b in
                                                       zip(B.bdays(date(2026, 11, 2), date(2026, 12, 31)),
                                                           B.bdays(date(2026, 11, 2), date(2026, 12, 31))[1:])), abs=1e-3)


def test_excess_and_interest_compound_and_months_add_up():
    mb = _mb(5.0)
    days = B.bdays(date(2026, 11, 2), date(2027, 1, 29))
    ser = [[d.isoformat(), 100 * (1.0005 ** i)] for i, d in enumerate(days)]
    o = B.add_total_return({"series": copy.deepcopy(ser)}, mb, date(2027, 1, 29))
    assert o["series"] == ser                                          # the excess series is untouched
    assert o["total_since_start_pct"] > o["excess_since_start_pct"] > 0
    rows = o["monthly_tbill"]
    assert [r["month"] for r in rows] == ["2026-11", "2026-12", "2027-01"]
    for r in rows:
        assert (1 + r["total_pct"] / 100) == pytest.approx((1 + r["excess_pct"] / 100) * (1 + r["tbill_pct"] / 100), abs=1e-6)
        assert 0.3 < r["tbill_pct"] < 0.5                              # about 5%/12 a month
    assert "display only" in o["tbill_note"].lower() and "excess returns" in o["tbill_note"]


def test_algorithm_sparse_points_accrue_daily_interest_between_them():
    mb = _mb(4.0)
    ser = [["2026-11-30", 100.0, "official"], ["2026-12-31", 101.0, "official"]]
    tot = B.total_return(ser, mb)
    cash = B.cash_index(mb, date(2026, 11, 30), date(2026, 12, 31))
    assert tot[-1][1] == pytest.approx(100 * (1 + 0.01 + (cash[-1][1] / 100 - 1)), abs=1e-3)


def test_fund_evaluation_ignores_total_return():
    from test_fund import books
    b = books()
    f1 = F.build_fund(copy.deepcopy(b), date(2027, 9, 15))
    for k in ("algorithm",):
        for v in b[k]["versions"]:
            B.add_total_return(v, _mb(), date(2027, 9, 15))
    B.add_total_return(b["janus"], _mb(), date(2027, 9, 15))
    f2 = F.build_fund(b, date(2027, 9, 15))
    assert f1["series"] == f2["series"] and f1["allocation"] == f2["allocation"] and f1["correlation"] == f2["correlation"]


def test_no_tbill_marks_means_no_interest():
    ser = [["2026-11-02", 100.0], ["2026-11-03", 101.0]]
    assert B.total_return(ser, B.MarkBook([]))[-1][1] == pytest.approx(101.0)
