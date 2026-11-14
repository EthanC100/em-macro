"""Q005: a leg-based spread mark pairs both legs on the same date.

ES-DE on 4 Nov 2026 was recorded as 57.4bp: ES10Y's 4 Nov close minus DE10Y's 9 Nov close, dated 4 Nov. On one
close it was 52.4bp. The rule: the spread is dated at the latest date on which both legs have an observation (each
leg's history plus its latest mark) and uses both legs' values on that date. If the legs have no common date, the
spread source fails and the next source (the instrument's fallback) or the previous mark is used.
Made-up data only; no network, no live files."""
from datetime import date

from ledger import marks

REG = [{"instrument": "XA10Y", "unit": "% yield", "frequency": "daily", "source": "fred", "source_id": "QA",
        "fallback_source": "", "fallback_id": ""},
       {"instrument": "XB10Y", "unit": "% yield", "frequency": "daily", "source": "fred", "source_id": "QB",
        "fallback_source": "", "fallback_id": ""},
       {"instrument": "XA-XB", "unit": "bp", "frequency": "daily", "source": "spread", "source_id": "XA10Y-XB10Y",
        "fallback_source": "", "fallback_id": ""}]


def _get(series: dict[str, str]):
    def get(url, **k):
        for sid, body in series.items():
            if url.endswith(f"id={sid}"):
                return body.encode()
        raise RuntimeError("down")
    return get


def _by(out):
    return {m["instrument"]: m for m in out}


def test_q005_spread_legs_same_date():
    # leg A last observed 4 Nov; leg B has 4 Nov (3.38) and a later 9 Nov (3.33)
    get = _get({"QA": "d,A\n2026-11-03,3.95\n2026-11-04,3.904\n",
                "QB": "d,B\n2026-11-03,3.40\n2026-11-04,3.38\n2026-11-09,3.33\n"})
    by = _by(marks.fetch_all(REG, date(2026, 11, 10), get=get))
    s = by["XA-XB"]
    assert s["date"] == "2026-11-04"
    assert float(s["value"]) == round((3.904 - 3.38) * 100, 2), s  # 52.4, not (3.904 - 3.33) * 100 = 57.4
    assert "3.38 (2026-11-04)" in s["note"] and "3.33" not in s["note"], s["note"]
    # the spread's history pairs the legs on each common date too
    assert dict(s["_history"]) == {date(2026, 11, 3): round((3.95 - 3.40) * 100, 2)}


def test_q005_latest_common_date_wins():
    # B's 4 Nov is missing (a holiday in B's market): the spread uses 3 Nov, the latest date both legs have
    get = _get({"QA": "d,A\n2026-11-03,3.95\n2026-11-04,3.904\n",
                "QB": "d,B\n2026-11-03,3.40\n2026-11-05,3.36\n"})
    s = _by(marks.fetch_all(REG, date(2026, 11, 10), get=get))["XA-XB"]
    assert s["date"] == "2026-11-03" and float(s["value"]) == 55.0, s


def test_q005_kept_previous_leg_pairs_with_history():
    # leg A's source is down and its previous mark (no history) is kept; B's history has A's date
    get = _get({"QB": "d,B\n2026-11-04,3.38\n2026-11-09,3.33\n"})
    prev = {"XA10Y": {"date": "2026-11-04", "instrument": "XA10Y", "value": "3.904", "unit": "% yield",
                      "frequency": "daily", "source": "fred QA", "source_url": "", "fetched_at": "", "note": ""}}
    s = _by(marks.fetch_all(REG, date(2026, 11, 10), get=get, previous=prev))["XA-XB"]
    assert s["date"] == "2026-11-04" and float(s["value"]) == 52.4, s


def test_q005_no_common_date_fails_the_spread_source():
    # no common date: no spread from the legs; the previous spread mark is kept, else no mark
    get = _get({"QA": "d,A\n2026-11-04,3.904\n", "QB": "d,B\n2026-11-09,3.33\n"})
    s = _by(marks.fetch_all(REG, date(2026, 11, 10), get=get))["XA-XB"]
    assert s["value"] == "" and "no common date" in s["note"], s
    prev = {"XA-XB": {"date": "2026-11-03", "instrument": "XA-XB", "value": "55", "unit": "bp",
                      "frequency": "daily", "source": "spread XA10Y-XB10Y", "source_url": "", "fetched_at": "",
                      "note": ""}}
    s = _by(marks.fetch_all(REG, date(2026, 11, 10), get=get, previous=prev))["XA-XB"]
    assert s["value"] == "55" and s["date"] == "2026-11-03" and "kept previous mark" in s["note"], s
