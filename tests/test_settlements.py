"""ledger/settlements.py: Databento final settlements into the private store, quoted first, US$1 daily cap."""
import json
from datetime import date, datetime, timezone

import pandas as pd
import pytest

from ledger import settlements as ST


class FakeClient:
    """Stands in for databento.Historical: symbology, metadata (cost, range) and timeseries."""

    def __init__(self, rows, cost=0.0001, end="2026-11-10T06:00:00.000000000Z", known=None):
        self.rows, self.cost, self.end, self.known, self.calls = rows, cost, end, known, []
        outer = self

        class Sym:
            def resolve(self, **kw):
                outer.calls.append(("resolve", kw))
                ok = [s for s in kw["symbols"] if outer.known is None or s in outer.known]
                return {"result": {s: [{"s": "1"}] for s in ok}, "not_found": [s for s in kw["symbols"] if s not in ok]}

        class Meta:
            def get_cost(self, **kw):
                outer.calls.append(("cost", kw))
                return outer.cost

            def get_dataset_range(self, **kw):
                return {"end": outer.end, "schema": {"statistics": {"end": outer.end}}}

        class TS:
            def get_range(self, **kw):
                outer.calls.append(("get_range", kw))

                class R:
                    def to_df(self, map_symbols=True):
                        df = pd.DataFrame(outer.rows)
                        return df[df["symbol"].isin(kw["symbols"])].set_index("ts_recv")
                return R()

        self.symbology, self.metadata, self.timeseries = Sym(), Meta(), TS()


def _stat(sym, day, price, final=True, recv_h=23):
    return {"ts_recv": pd.Timestamp(f"{day} {recv_h}:00", tz="UTC"), "ts_ref": pd.Timestamp(day, tz="UTC"),
            "symbol": sym, "stat_type": 3, "stat_flags": 3 if final else 2, "price": price}


ROWS = [_stat("BZH7", "2026-11-06", 93.10, final=False, recv_h=19), _stat("BZH7", "2026-11-06", 93.25),
        _stat("BZH7", "2026-11-09", 95.5), _stat("BZH7", "2026-11-09", 95.0, final=False, recv_h=19),
        {**_stat("BZH7", "2026-11-09", 1.0), "stat_type": 4}]                   # not a settlement


def test_final_settlement_only_and_private_store(tmp_path):
    c = FakeClient(ROWS)
    res = ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path, c=c)
    rows = ST.read(tmp_path)
    assert [(r["date"], r["settle"]) for r in rows] == [("2026-11-06", "93.25"), ("2026-11-09", "95.5")]
    assert rows[0]["source"].startswith("Databento GLBX.MDP3 statistics, final settlement")
    assert res["stored"] == 2 and not res["refused"]
    kinds = [k for k, _ in c.calls]
    assert kinds.index("cost") < kinds.index("get_range")          # quoted before every request
    spend = [json.loads(x) for x in (tmp_path / ST.SPEND_FILE).read_text().splitlines()]
    assert spend[-1]["downloaded"] and spend[-1]["quote_usd"] == 0.0001
    # nothing new: only the days after the last stored one are requested
    ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path, c=c)
    last_get = [kw for k, kw in c.calls if k == "get_range"][-1]
    assert last_get["start"].startswith("2026-11-10")


def test_daily_cap_refuses_and_is_shared(tmp_path):
    c = FakeClient(ROWS, cost=0.6)
    a = ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path, c=c, purpose="me")
    assert a["stored"] == 2
    b = ST.fetch({("WTI", "2027-01"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path,
                 c=FakeClient([_stat("CLF7", "2026-11-06", 87.0)], cost=0.6), purpose="janus")
    assert b["refused"] and "above US$1.00" in b["log"][-1]
    assert ST.read(tmp_path) and all(r["product"] == "BRENT" for r in ST.read(tmp_path))
    assert ST.spent_today(tmp_path, date(2026, 11, 10)) == pytest.approx(0.6)
    assert ST.spent_today(tmp_path, date(2026, 11, 11)) == 0.0     # a new UTC day
    # a single request above the cap is refused outright
    big = FakeClient([], cost=1.5)
    r = ST.fetch({("WTI", "2027-01"): date(2026, 11, 6)}, date(2026, 11, 11), tmp_path, c=big)
    assert r["refused"] and not any(k == "get_range" for k, _ in big.calls)


def test_no_store_fetches_nothing():
    c = FakeClient(ROWS)
    res = ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 10), store=None, c=c)
    assert res["stored"] == 0 and "no private store" in res["log"][0] and c.calls == []


def test_two_digit_year_symbols_are_resolved(tmp_path):
    c = FakeClient([_stat("NGF27", "2026-11-06", 3.9)], known={"NGF27"})
    res = ST.fetch({("NATGAS", "2027-01"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path, c=c)
    assert res["stored"] == 1 and ST.read(tmp_path)[0]["contract_month"] == "2027-01"
    assert "NGF27" in [kw for k, kw in c.calls if k == "get_range"][0]["symbols"]


def test_calendar():
    assert ST.contract_code("BRENT", "2027-03") == "BZH27" and ST.raw_symbols("CORN", "2027-03") == ["ZCH7", "ZCH27"]
    assert ST.notice_date("BRENT", 2027, 3) == date(2027, 1, 31)
    assert ST.notice_date("GOLD", 2026, 12) == date(2026, 11, 30)
    assert ST.front_month("GOLD", date(2026, 11, 6)) == "2027-02"          # Dec notice 30 Nov is within 35 days
    assert ST.front_month("CORN", date(2026, 11, 6)) == "2027-03"
    assert ST.front_month("WTI", date(2026, 11, 6)) == "2027-01"
