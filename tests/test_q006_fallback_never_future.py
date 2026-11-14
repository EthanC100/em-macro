"""Q006: a monthly-panel fallback mark is never dated in the future and never replaces a newer daily mark.

On 9 Nov 2026 mindicador.cl timed out and CLP fell back to the monthly panel, whose November value
``fetch_panel_monthly`` dates at the month end: the row ``2026-11-30,CLP,980.59,...,monthly,panel_monthly ...``
was written three weeks ahead of the run, replaced the 6 Nov daily mark (970.94) as CLP's latest mark, and with a
negative age was never flagged stale. The rules:
1. a fallback is never dated after the run's day: a panel month that has not ended is not used (the panel's last
   month end on or before the day is, and the usual "never replace a newer daily mark" guard then applies);
2. a monthly fallback row already in the file dated after the day it was fetched (the existing 30 Nov CLP row)
   never wins over another mark of the instrument: latest marks, marks.json and the books show the newest daily;
3. a monthly *primary* (an instrument with no daily source) keeps its month-end date, as documented.
Made-up panel and marks in a temporary directory, stubbed sources; never data/ledger or data/processed."""
import csv
from datetime import date

from ledger import build as B
from ledger import books as BK
from ledger import marks as M

TODAY = date(2026, 11, 9)
CLP_ROW = {"instrument": "CLP", "country": "Chile", "iso3": "CHL", "book": "fx", "kind": "fx", "unit": "CLP per USD",
           "frequency": "daily", "source": "mindicador", "source_id": "dolar", "source_url": "https://mindicador.cl/api/dolar",
           "fallback_source": "panel_monthly", "fallback_id": "fx_per_usd_end:CHL", "aliases": "USD/CLP|USDCLP|CLP"}
ID10Y_ROW = {"instrument": "ID10Y", "country": "Indonesia", "iso3": "IDN", "book": "bond", "kind": "yield",
             "unit": "% yield", "frequency": "monthly", "source": "panel_monthly", "source_id": "y10:IDN",
             "source_url": "", "fallback_source": "", "fallback_id": "", "aliases": "ID10Y"}
DAILY_6NOV = {"date": "2026-11-06", "instrument": "CLP", "value": "970.94", "unit": "CLP per USD", "frequency": "daily",
              "source": "mindicador dolar", "source_url": "https://mindicador.cl/api/dolar",
              "fetched_at": "2026-11-08T16:06:38+00:00", "note": ""}
DAILY_5NOV = {**DAILY_6NOV, "date": "2026-11-05", "value": "970.95", "fetched_at": "2026-11-06T04:09:32+00:00",
              "note": "recent history returned by the source"}
# the row ledger-daily wrote on 9 Nov (shape and dates as in data/ledger/marks.csv; the error text shortened)
BAD_30NOV = {"date": "2026-11-30", "instrument": "CLP", "value": "980.59", "unit": "CLP per USD", "frequency": "monthly",
             "source": "panel_monthly fx_per_usd_end:CHL", "source_url": "data/processed/country_month_panel.csv",
             "fetched_at": "2026-11-09T14:29:14+00:00",
             "note": "fallback panel_monthly fx_per_usd_end:CHL after: mindicador dolar: https://mindicador.cl/api/dolar: "
                     "timed out"}


def _panel(root, months=("2026-09", "2026-10", "2026-11")):
    p = root / "data/processed/country_month_panel.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    vals = {"2026-09": ("950.10", "6.70"), "2026-10": ("965.20", "6.55"), "2026-11": ("980.59", "6.45")}
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["month", "iso3", "fx_per_usd_end", "y10"])
        for m in months:
            w.writerow([m, "CHL", vals[m][0], ""])
            w.writerow([m, "IDN", "", vals[m][1]])
    return root


def _use_panel(monkeypatch, root):
    monkeypatch.setitem(M.FETCHERS, "panel_monthly", lambda spec, get=None: M.fetch_panel_monthly(spec, get, root=root))


def mindicador_down(url, **kw):
    raise RuntimeError(f"{url}: timed out")


def test_q006_fallback_never_future(tmp_path, monkeypatch):
    """9 Nov: the primary fails, the panel has November: no mark after today, the 6 Nov daily mark is kept."""
    _use_panel(monkeypatch, _panel(tmp_path))
    out = M.fetch_instrument(CLP_ROW, {}, {}, TODAY, mindicador_down, previous={"CLP": dict(DAILY_6NOV)})
    assert out["date"] <= TODAY.isoformat(), f"mark dated {out['date']}, after {TODAY}: {out}"
    assert (out["date"], out["value"], out["frequency"]) == ("2026-11-06", "970.94", "daily"), out
    assert out["note"].startswith("kept previous mark"), out["note"]

    # the whole run (fetch_all), and with no previous mark at all: still nothing after today
    run = {m["instrument"]: m for m in M.fetch_all([CLP_ROW], TODAY, get=mindicador_down,
                                                    previous={"CLP": dict(DAILY_6NOV)})}
    assert run["CLP"]["date"] == "2026-11-06", run["CLP"]
    fresh = M.fetch_instrument(CLP_ROW, {}, {}, TODAY, mindicador_down, previous={})
    assert fresh["date"] and fresh["date"] <= TODAY.isoformat(), fresh
    assert (fresh["date"], fresh["value"], fresh["frequency"]) == ("2026-10-31", "965.2", "monthly"), fresh
    assert not M.mark_can_act(fresh)

    # written to a marks file: no row after today, the 6 Nov daily row untouched and still the latest
    path = tmp_path / "marks.csv"
    M.write_marks([dict(DAILY_6NOV)], path)
    M.write_marks([out], path)
    rows = M.read_marks(path)
    assert all(r["date"] <= TODAY.isoformat() for r in rows), rows
    assert M.latest_marks(path)["CLP"]["date"] == "2026-11-06"


def test_q006_existing_future_fallback_row_never_wins(tmp_path, monkeypatch):
    """The 30 Nov CLP row already in the file: latest marks, marks.json and the books show the newest daily mark."""
    rows = [dict(DAILY_5NOV), dict(DAILY_6NOV), dict(BAD_30NOV)]
    latest = M.latest_marks(rows=rows)
    assert (latest["CLP"]["date"], latest["CLP"]["value"], latest["CLP"]["frequency"]) == ("2026-11-06", "970.94", "daily")

    # marks.json
    monkeypatch.setattr(B, "read_marks", lambda *a, **k: [dict(r) for r in rows])
    monkeypatch.setattr(B, "load_registry", lambda *a, **k: [dict(CLP_ROW)])
    item = next(i for i in B.build_marks(TODAY)["items"] if i["instrument"] == "CLP")
    assert (item["date"], item["value"], item["frequency"]) == ("2026-11-06", 970.94, "daily"), item
    assert item["age_days"] >= 0

    # books.json: an open CLP decision is marked at the 6 Nov daily mark; the algorithm's mark lookups and mark
    # history never use the 30 Nov row (not even on or after 30 Nov)
    dec = {"id": "D999", "date": "2026-11-02", "instrument": "USD/CLP", "action": "Buy", "entry_level": "960",
           "stop": "940", "size_pct": "1"}
    lm = M.live_mark(dec, [dict(CLP_ROW)], latest)
    assert (lm["mark_date"], lm["mark"], lm["mark_can_act"]) == ("2026-11-06", 970.94, True), lm
    mb = BK.MarkBook(rows=[dict(r) for r in rows])
    assert [x[0].isoformat() for x in mb.series("CLP", all_marks=True)] == ["2026-11-05", "2026-11-06"]
    assert mb.on("CLP", date(2026, 12, 1), all_marks=True)[0] == date(2026, 11, 6)
    est = BK.algo_estimate([{"instrument": "CLP", "size_pct_of_capital": 10.0, "book": "fx"}], mb, "2026-11",
                           date(2026, 11, 30))
    p = est["positions"][0]
    assert p["mark_date"] == "2026-11-06", p
    assert all(h[0] <= "2026-11-06" for h in p["mark_history"]), p["mark_history"]


def test_q006_monthly_primaries_keep_month_end_dates(tmp_path, monkeypatch):
    """An instrument with no daily source is still dated at the month end of its panel value (documented)."""
    _use_panel(monkeypatch, _panel(tmp_path))
    out = M.fetch_instrument(ID10Y_ROW, {}, {}, TODAY, mindicador_down, previous={})
    assert (out["date"], out["value"], out["frequency"], out["note"]) == ("2026-11-30", "6.45", "monthly", ""), out
    _use_panel(monkeypatch, _panel(tmp_path / "oct", months=("2026-09", "2026-10")))
    out = M.fetch_instrument(ID10Y_ROW, {}, {}, TODAY, mindicador_down, previous={})
    assert (out["date"], out["value"], out["frequency"]) == ("2026-10-31", "6.55", "monthly"), out
    # its rows are not treated as future fallbacks: the 30 Nov primary row stays the latest mark
    prim = {"date": "2026-11-30", "instrument": "ID10Y", "value": "6.45", "unit": "% yield", "frequency": "monthly",
            "source": "panel_monthly y10:IDN", "source_url": "", "fetched_at": "2026-11-09T14:29:14+00:00", "note": ""}
    older = {**prim, "date": "2026-10-31", "value": "6.55"}
    assert M.latest_marks(rows=[older, prim])["ID10Y"]["date"] == "2026-11-30"
    assert [x[0].isoformat() for x in BK.MarkBook(rows=[older, prim]).series("ID10Y", all_marks=True)] == \
        ["2026-10-31", "2026-11-30"]
