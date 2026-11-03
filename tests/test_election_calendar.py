"""Tests for the election calendar: infobox date parsing and update rules."""
import datetime as dt

import pandas as pd

from em_macro.election_tracker.calendar import apply_infobox, infobox_date
from em_macro.election_tracker.common import CAL_COLS, load_calendar


def test_calendar_file_shape():
    cal = load_calendar()
    assert list(cal.columns) == CAL_COLS
    assert cal["id"].is_unique
    mx = cal[cal["id"] == "mx-2027-legislative"].iloc[0]
    assert mx["date"] == "2027-06-06" and mx["currency"] == "MXN" and mx["status"] == "scheduled"
    assert set(cal["status"]) <= {"scheduled", "due_by", "held", "postponed"}
    for d in cal["date"]:
        assert dt.date(2026, 11, 3) <= dt.date.fromisoformat(d) <= dt.date(2028, 11, 3)


def test_infobox_plain_and_template_dates():
    assert infobox_date("| election_date = 6 June 2027\n")[1:] == (dt.date(2027, 6, 6), False)
    assert infobox_date("| election_date = {{Start date|2028|5|8}}\n")[1:] == (dt.date(2028, 5, 8), False)
    assert infobox_date("| election_date = May 8, 2028<ref>x</ref>\n")[1:] == (dt.date(2028, 5, 8), False)


def test_infobox_deadlines_and_month_only():
    assert infobox_date("| election_date = By 11 November 2027\n")[1:] == (dt.date(2027, 11, 11), True)
    assert infobox_date("| election_date = No later than 12 April 2028\n")[1:] == (dt.date(2028, 4, 12), True)
    assert infobox_date("| election_date = By January 2028\n")[1] is None
    assert infobox_date("| election_date = On or before {{Start date|2028|02||df=y}}\n")[1] is None
    assert infobox_date("no infobox") == (None, None, False)


def _row(date, status):
    return pd.Series({"id": "x", "date": date, "status": status})


def test_apply_infobox_rules():
    # a set date upgrades due_by -> scheduled
    new, ch = apply_infobox(_row("2027-11-11", "due_by"), dt.date(2027, 10, 17), False)
    assert new["date"] == "2027-10-17" and new["status"] == "scheduled" and ch
    # a deadline never downgrades scheduled
    new, ch = apply_infobox(_row("2028-04-12", "scheduled"), dt.date(2028, 4, 12), True)
    assert new["status"] == "scheduled" and ch == ""
    # month-only text changes nothing
    new, ch = apply_infobox(_row("2028-01-31", "due_by"), None, True)
    assert ch == "" and new["date"] == "2028-01-31"
