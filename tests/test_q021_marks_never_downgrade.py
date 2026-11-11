"""Q021 (HIGH PRIORITY, filed by Ethan's session 2026-11-11): a failed fetch ("kept previous mark") or a re-fetch of
the same old observation ("stale: ...") overwrites the earlier first-hand row for that instrument and date, and
mark_can_act then rejects it: MXN 2026-11-06 (ledger-daily, 9 Nov 20:12 UTC, commit b369511) and BRENT, HEATOIL,
NATGAS, RBOB, WTI 2026-11-03 (11 Nov 03:18 UTC, commit 26e0eae).

Tests 1 and 2 reproduced the bug (strict xfails until ledger/marks.py was fixed: write_marks keeps an existing row
that mark_can_act accepts when the new row for the same instrument and date would fail it); test 3 is the behaviour
the fix must keep, and test 4 pins that a row that cannot act is still replaced by the newest fetch.
A temporary marks file and stubbed sources only: never data/ledger."""
import csv
from datetime import date

from ledger import marks as M

MXN_ROW = {"instrument": "MXN", "country": "Mexico", "iso3": "MEX", "book": "fx", "kind": "fx", "unit": "MXN per USD",
           "frequency": "daily", "source": "banxico", "source_id": "SF43718", "source_url": "https://www.banxico.org.mx",
           "fallback_source": "fred", "fallback_id": "DEXMXUS"}
GOOD_6NOV = {"date": "2026-11-06", "instrument": "MXN", "value": "18.6297", "unit": "MXN per USD", "frequency": "daily",
             "source": "banxico SF43718", "source_url": "https://www.banxico.org.mx", "fetched_at": "2026-11-06T16:51:02+00:00",
             "note": ""}
FRED_OLD = "observation_date,DEXMXUS\n2026-10-30,18.71\n"


def write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=M.MARK_COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in M.MARK_COLUMNS})


def row(path, inst, d):
    return next(r for r in M.read_marks(path) if r["instrument"] == inst and r["date"] == d)


def banxico_down(url, **kw):
    if "fred" in url:
        return FRED_OLD.encode()
    raise RuntimeError(f"{url}: Remote end closed connection without response")


def test_a_failed_fetch_keeps_the_earlier_first_hand_mark(tmp_path):
    """MXN's 6 Nov case: Banxico fails on 9 Nov, FRED's fallback is older, so the run keeps the previous mark."""
    path = tmp_path / "marks.csv"
    write(path, [GOOD_6NOV])
    kept = M.fetch_instrument(MXN_ROW, {}, {}, date(2026, 11, 9), banxico_down, previous={"MXN": dict(GOOD_6NOV)})
    assert kept["note"].startswith("kept previous mark")                      # the run still reports the failure
    M.write_marks([kept], path)
    r = row(path, "MXN", "2026-11-06")
    assert (r["value"], r["note"], r["fetched_at"]) == ("18.6297", "", GOOD_6NOV["fetched_at"])
    assert M.mark_can_act(r)


def test_a_stale_refetch_of_the_same_observation_keeps_the_first_hand_mark(tmp_path):
    """The energy case: FRED still ends at 3 Nov on 11 Nov, so the re-fetched row is flagged stale."""
    wti = {"instrument": "WTI", "unit": "USD per bbl", "frequency": "daily", "source": "fred", "source_id": "DCOILWTICO"}
    good = {"date": "2026-11-03", "instrument": "WTI", "value": "99.64", "unit": "USD per bbl", "frequency": "daily",
            "source": "fred DCOILWTICO", "source_url": "https://fred.stlouisfed.org", "note": "",
            "fetched_at": "2026-11-04T10:09:00+00:00"}
    path = tmp_path / "marks.csv"
    write(path, [good])
    again = M.fetch_instrument(wti, {}, {}, date(2026, 11, 11),
                               lambda url, **kw: b"observation_date,DCOILWTICO\n2026-11-03,99.64\n")
    assert "stale" in again["note"]
    M.write_marks([again], path)
    r = row(path, "WTI", "2026-11-03")
    assert (r["value"], r["note"], r["fetched_at"]) == ("99.64", "", good["fetched_at"])
    assert M.mark_can_act(r)


def test_a_newer_first_hand_value_for_the_same_date_still_replaces_the_old_one(tmp_path):
    path = tmp_path / "marks.csv"
    write(path, [GOOD_6NOV])
    M.write_marks([{**GOOD_6NOV, "value": "18.6301", "fetched_at": "2026-11-07T16:51:00+00:00"}], path)
    r = row(path, "MXN", "2026-11-06")
    assert r["value"] == "18.6301" and M.mark_can_act(r)


def test_a_row_that_cannot_act_is_still_replaced_by_the_newest_fetch(tmp_path):
    """Only a first-hand row is protected: an earlier stale row for the same date is replaced as before."""
    path = tmp_path / "marks.csv"
    stale = {**GOOD_6NOV, "note": "stale: last observation 6 days old"}
    write(path, [stale])
    M.write_marks([{**GOOD_6NOV, "note": "kept previous mark; banxico down", "fetched_at": "2026-11-09T20:12:00+00:00"}],
                  path)
    assert row(path, "MXN", "2026-11-06")["fetched_at"] == "2026-11-09T20:12:00+00:00"
    M.write_marks([{**GOOD_6NOV, "fetched_at": "2026-11-10T16:51:00+00:00"}], path)
    r = row(path, "MXN", "2026-11-06")
    assert r["fetched_at"] == "2026-11-10T16:51:00+00:00" and M.mark_can_act(r)
