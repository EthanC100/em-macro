"""Config change C09 (approved by Ethan 2026-11-11, before C08's first review; docs/config_changes.md):
1. US10Y and GB10Y marks lagged two to three business days behind (FRED DGS10 republishes Treasury's 10-year
   constant-maturity yield a business day late, and ledger-daily runs before it updates; the Bank of England's
   IUDMNPY is published two to three business days late and its database refuses cloud clients). US10Y now comes
   from Treasury's daily par yield curve CSV (identical values, fallback FRED DGS10), GB10Y from the Riksbank's
   benchmark gilt yield (GBGVB10Y).
2. The watchlist adds BRL (BCB PTAX) and MXN (Banxico FIX); no gold (no free, republishable daily mark).
3. The fund rule counts one call per correlation cluster (G10 yields, USD vs G10 FX, EM FX, gold) per window
   (cluster tests are in tests/test_janus_c08.py with the rest of the fund rule).

Every test here fails before C09 and passes after."""
import csv
from datetime import date
from pathlib import Path

import pytest

from ledger import janus as J
from ledger import marks as M

ROOT = Path(__file__).resolve().parents[1]
UST = ('Date,"1 Mo","1.5 Month","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr",'
       '"30 Yr"\n'
       "11/10/2026,4.05,4.16,4.21,4.30,4.28,4.38,4.56,4.73,4.74,4.81,4.89,4.98,5.39,5.35\n"
       "11/09/2026,4.04,4.13,4.19,4.24,4.20,4.26,4.38,4.56,4.58,4.67,4.76,4.88,5.29,5.26\n"
       "11/06/2026,4.02,4.07,4.15,4.19,4.19,4.23,4.33,4.51,4.59,4.64,4.74,4.86,5.29,5.26\n")
FRED_LAGGED = "observation_date,DGS10\n2026-11-05,4.84\n2026-11-06,4.86\n"     # what ledger-daily saw on 10 Nov


def registry():
    return {r["instrument"]: r for r in M.load_registry()}


def fake(responses: dict[str, str]):
    """A get() that answers by URL substring, and fails for anything else (a source that is down)."""
    def get(url, **kw):
        for k, v in responses.items():
            if k in url:
                return v.encode()
        raise RuntimeError(f"{url}: down")
    return get


# ----------------------------------------------------------------------------- 1. the mark sources
def test_the_treasury_par_curve_parser_reads_the_10_year_column():
    pts, url = M.ustreasury_history("10 Yr", None, fake({"daily-treasury-rates.csv/2026": UST}), today=date(2026, 11, 11))
    assert pts == [(date(2026, 11, 6), 4.86), (date(2026, 11, 9), 4.88), (date(2026, 11, 10), 4.98)]
    assert "daily_treasury_yield_curve" in url
    assert M.ustreasury_history("10 Yr", date(2026, 11, 9), fake({"2026": UST}), today=date(2026, 11, 11))[0][0][0] == \
        date(2026, 11, 9)
    with pytest.raises(ValueError, match="no Date / 10 Yr column"):
        M.ustreasury_history("10 Yr", None, fake({"2026": "Date,2 Yr\n11/10/2026,4.7\n"}), today=date(2026, 11, 11))


def test_early_january_reads_the_previous_year_too():
    seen = []
    def get(url, **kw):
        seen.append(url)
        return (UST if "/2026/" in url else UST.split("\n")[0] + "\n").encode()
    pts, _ = M.ustreasury_history("10 Yr", None, get, today=date(2027, 1, 5))
    assert any("/2026/" in u for u in seen) and any("/2027/" in u for u in seen) and pts[-1] == (date(2026, 11, 10), 4.98)


def test_us10y_and_gb10y_use_the_faster_sources():
    reg = registry()
    us, gb = reg["US10Y"], reg["GB10Y"]
    assert (us["source"], us["source_id"], us["fallback_source"], us["fallback_id"]) == ("ustreasury", "10 Yr", "fred",
                                                                                        "DGS10")
    assert (gb["source"], gb["source_id"]) == ("riksbank", "GBGVB10Y") and gb["fallback_source"] == "panel_monthly"
    assert us["frequency"] == gb["frequency"] == "daily"
    assert "ustreasury" in M.FETCHERS and "ustreasury" in M.HISTORY


def test_on_review_day_us10y_is_marked_from_the_previous_business_day_not_two_days_back():
    """At ledger-daily's run on 11 Nov, FRED still ended at 6 Nov (the 10 Nov run's view) while Treasury's curve has
    10 Nov: the mark is the previous business day's, and it can act."""
    reg = registry()
    get = fake({"daily-treasury-rates.csv": UST, "fred.stlouisfed.org": FRED_LAGGED})
    m = M.fetch_instrument(reg["US10Y"], {}, {}, date(2026, 11, 11), get)
    assert (m["date"], m["value"], m["source"], m["frequency"]) == ("2026-11-10", "4.98", "ustreasury 10 Yr", "daily")
    assert M.mark_can_act(m) and dict(m["_history"])[date(2026, 11, 9)] == 4.88
    assert J._stale_weekdays(date(2026, 11, 10), date(2026, 11, 11)) == 0
    # Treasury down: FRED DGS10 (same series, a business day later) is the fallback, flagged as such
    fb = M.fetch_instrument(reg["US10Y"], {}, {}, date(2026, 11, 11), fake({"fred.stlouisfed.org": FRED_LAGGED}))
    assert (fb["date"], fb["source"]) == ("2026-11-06", "fred DGS10") and fb["note"].startswith("fallback fred DGS10")


def test_the_treasury_curve_and_fred_dgs10_are_the_same_numbers():
    """The stored FRED marks for 5-6 Nov equal Treasury's 10-year CMT on those dates (the series is the same)."""
    rows = {r["date"]: r["value"] for r in csv.DictReader((ROOT / "data/ledger/marks.csv").open())
            if r["instrument"] == "US10Y" and r["source"] == "fred DGS10"}
    pts = dict(M.ustreasury_history("10 Yr", None, fake({"2026": UST}), today=date(2026, 11, 11))[0])
    assert float(rows["2026-11-06"]) == pts[date(2026, 11, 6)]


def test_gb10y_reads_the_riksbank_benchmark_gilt():
    js = ('[{"date":"2026-11-06","value":5.1559},{"date":"2026-11-09","value":5.1396},'
          '{"date":"2026-11-10","value":5.1702}]')
    m = M.fetch_instrument(registry()["GB10Y"], {}, {}, date(2026, 11, 11), fake({"Observations/GBGVB10Y": js}))
    assert (m["date"], m["value"], m["source"]) == ("2026-11-10", "5.1702", "riksbank GBGVB10Y") and M.mark_can_act(m)


# ----------------------------------------------------------------------------- 2. BRL and MXN; no gold
def test_the_watchlist_adds_brl_and_mxn_on_central_bank_fixings_and_stays_at_11_or_fewer():
    wl = {w["instrument"]: w for w in J.load_watchlist()}
    assert len(wl) <= 11 and {"BRL", "MXN"} <= set(wl)
    reg = registry()
    assert (reg["BRL"]["source"], reg["BRL"]["source_id"]) == ("bcb_sgs", "1")             # BCB PTAX (sell)
    assert (reg["MXN"]["source"], reg["MXN"]["source_id"]) == ("banxico", "SF43718")       # Banxico FIX
    assert "PTAX" in wl["BRL"]["resolution_source"] and "FIX" in wl["MXN"]["resolution_source"]
    for i in ("BRL", "MXN"):
        assert J.UNIVERSE[i]["asset_class"] == "fx" and J.UNIVERSE[i]["cost"] == 0.001
        assert wl[i]["yes_if"] == "lower" and wl[i]["cluster"] == "em_fx" and wl[i]["stop"]["unit"] == "percent"
    assert not any(J.is_future(i) or "GOLD" in i for i in wl)                             # no licensed gold mark
    doc = (ROOT / "janus/watchlist.yaml").read_text(encoding="utf-8")
    assert "ICE Benchmark Administration" in doc and "31 January 2022" in doc


def test_the_clusters_partition_the_watchlist():
    cl = J.load_clusters()
    assert list(cl) == ["g10_yields", "usd_g10_fx", "em_fx", "gold"]
    assert cl["g10_yields"] == ["US10Y", "GB10Y", "DE10Y", "JP10Y"]
    assert cl["usd_g10_fx"] == ["EUR", "GBP", "JPY", "AUD"] and cl["em_fx"] == ["BRL", "MXN"] and cl["gold"] == []
    members = [i for ms in cl.values() for i in ms]
    assert sorted(members) == sorted(w["instrument"] for w in J.load_watchlist()) and len(members) == len(set(members))


# ----------------------------------------------------------------------------- docs
def test_c09_is_recorded():
    doc = (ROOT / "docs/config_changes.md").read_text(encoding="utf-8")
    assert "| C09 | 2026-11-11 |" in doc and "## C09" in doc and "Approved by Ethan on 2026-11-11" in doc
    fund = (ROOT / "docs/fund/allocation.md").read_text(encoding="utf-8")
    assert "one call per correlation cluster per non-overlapping 20-trading-day window" in fund
    rb = (ROOT / "docs/janus/daily_review.md").read_text(encoding="utf-8")
    assert "BRL" in rb and "MXN" in rb and "C09" in rb
