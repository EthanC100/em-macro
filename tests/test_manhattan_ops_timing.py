"""Manhattan ops, component 2: registration time, first eligible observation, prospective eligibility (O-06 to O-10).
No network: the GitHub API reply and the witness are given as data."""
from datetime import date, datetime, timezone

import pytest

from manhattan.ops import timing as T

H = "a" * 64
UTC = timezone.utc


def t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def tim(cal="us_fed_fx", minutes=0, sessions=0, cutoff="2026-01-02", declared=None, horizon=1):
    d = {"calendar": cal, "horizon_sessions": horizon, "execution_lag": {"minutes": minutes, "sessions": sessions},
         "data_cutoff": cutoff}
    if declared:
        d["declared_first_observation"] = declared
    return d


def witnessed(at):
    return T.Witness("opentimestamps", H, t(at), True)


def go(merged, witness="same", **kw):
    w = witnessed(merged) if witness == "same" else witness
    return T.assess(prediction_id="AP-1", spec_hash="b" * 64, manifest_hash=H, merged=t(merged), merge_commit="c" * 40,
                    witness=w, timing=tim(**kw))


# ---- calendars

def test_holiday_rules_2026():
    fed, nyse = T.us_federal_holidays(2026), T.nyse_holidays(2026)
    assert date(2026, 11, 26) in fed and date(2026, 11, 26) in nyse                 # Thanksgiving
    assert date(2026, 4, 3) in nyse and date(2026, 4, 3) not in fed                  # Good Friday: exchange only
    assert date(2026, 11, 11) in fed and date(2026, 11, 11) not in nyse              # Veterans Day: Fed only
    assert date(2026, 7, 3) in nyse and date(2026, 7, 3) not in fed                  # 4 July on a Saturday
    assert T.easter(2026) == date(2026, 4, 5) and T.easter(2025) == date(2025, 4, 20)


def test_close_in_utc_follows_daylight_saving():
    cal = T.calendar("us_fed_fx")
    assert cal.close_utc(date(2026, 7, 15)) == t("2026-07-15T21:00:00Z")            # 17:00 EDT
    assert cal.close_utc(date(2026, 11, 18)) == t("2026-11-18T22:00:00Z")           # 17:00 EST


# ---- O-08 and O-10: first eligible observation

@pytest.mark.parametrize("merged, cal, minutes, sessions, expect", [
    ("2026-11-14T15:00:00Z", "us_fed_fx", 0, 0, "2026-11-16"),     # merged on a Saturday: Monday's close
    ("2026-11-25T23:00:00Z", "us_fed_fx", 0, 0, "2026-11-27"),     # after Wednesday's close, Thanksgiving next
    ("2026-04-02T22:00:00Z", "nyse", 0, 0, "2026-04-06"),          # Good Friday: the exchange is shut
    ("2026-04-02T22:00:00Z", "us_fed_fx", 0, 0, "2026-04-03"),     # ...the Fed's FX calendar is not
    ("2026-11-13T21:59:00Z", "us_fed_fx", 0, 0, "2026-11-13"),     # one minute before Friday's close
    ("2026-11-13T22:00:00Z", "us_fed_fx", 0, 0, "2026-11-16"),     # exactly at the close: strictly after, so Monday
    ("2026-11-13T22:01:00Z", "us_fed_fx", 0, 0, "2026-11-16"),     # one minute after
    ("2026-07-15T21:30:00Z", "us_fed_fx", 0, 0, "2026-07-16"),     # 17:30 EDT: after the close
    ("2026-11-18T21:30:00Z", "us_fed_fx", 0, 0, "2026-11-18"),     # the same UTC time is 16:30 EST: before it
    ("2026-11-13T20:00:00Z", "us_fed_fx", 180, 0, "2026-11-16"),   # a 3-hour lag carries it over the weekend
    ("2026-11-13T20:00:00Z", "us_fed_fx", 0, 1, "2026-11-16"),     # a one-session lag: Friday, then Monday
    ("2026-11-10T23:00:00Z", "us_fed_fx", 0, 0, "2026-11-12"),     # Veterans Day (Fed) skipped
])
def test_first_eligible_observation(merged, cal, minutes, sessions, expect):
    r = go(merged, cal=cal, minutes=minutes, sessions=sessions)
    assert r["first_eligible_observation"] == expect and r["eligible"], r


# ---- O-07: two sources, the later wins; provisional without a witness

def test_registration_is_the_later_source_and_provisional_without_witness():
    r = go("2026-11-13T15:00:00Z", witness=witnessed("2026-11-13T18:00:00Z"))
    assert r["registration_utc"] == "2026-11-13T18:00:00Z" and r["registration_status"] == "witnessed"
    assert r["sources"]["github_merged_at"] == "2026-11-13T15:00:00Z" and r["evidential_weight"] == 1
    p = go("2026-11-13T15:00:00Z", witness=None)
    assert p["registration_status"] == "provisional" and p["eligible"] and p["evidential_weight"] == 0
    u = go("2026-11-13T15:00:00Z", witness=T.Witness("opentimestamps", H, None, False))
    assert u["registration_status"] == "provisional"
    with pytest.raises(T.TimingError, match="different hash"):
        go("2026-11-13T15:00:00Z", witness=T.Witness("opentimestamps", "f" * 64, t("2026-11-13T16:00:00Z"), True))


# ---- O-09 and O-10: ineligible, with reasons, never dropped

def test_published_after_close_is_still_ineligible_once_the_close_has_passed():
    # Friday's H.10 value is published Monday 16:15; registration Friday 23:00 UTC is after the close, before it
    r = go("2026-11-13T23:00:00Z", declared="2026-11-13")
    assert r["first_observation_published_utc"] == "2026-11-16T21:15:00Z"
    assert not r["eligible"] and r["ineligible_reasons"] == ["window_begun_at_registration"]
    assert r["evidential_weight"] == 0


def test_late_merge_after_declared_window_began():
    r = go("2026-11-17T14:00:00Z", declared="2026-11-16")
    assert not r["eligible"] and "window_begun_at_registration" in r["ineligible_reasons"]
    assert r["first_eligible_observation"] == "2026-11-17"            # still computed and recorded


def test_witness_arriving_after_the_declared_start():
    r = go("2026-11-13T20:00:00Z", witness=witnessed("2026-11-13T23:00:00Z"), declared="2026-11-13")
    assert r["ineligible_reasons"] == ["witness_after_window_start"]
    ok = go("2026-11-13T20:00:00Z", witness=witnessed("2026-11-13T21:00:00Z"), declared="2026-11-13")
    assert ok["eligible"]


def test_declared_start_inside_execution_lag_and_not_a_session():
    r = go("2026-11-13T20:00:00Z", sessions=1, declared="2026-11-13")
    assert r["ineligible_reasons"] == ["first_observation_inside_execution_lag"]
    s = go("2026-11-13T15:00:00Z", declared="2026-11-21")              # a Saturday
    assert "declared_first_observation_not_a_session" in s["ineligible_reasons"]


def test_data_cutoff_rules():
    r = go("2026-11-13T15:00:00Z", cutoff="2026-11-14")
    assert {"data_cutoff_after_registration", "data_cutoff_inside_outcome_window"} <= set(r["ineligible_reasons"])
    ok = go("2026-11-13T15:00:00Z", cutoff="2026-11-12")               # through Thursday: fine for Friday's close
    assert ok["eligible"]
    edge = go("2026-11-13T15:00:00Z", cutoff="2026-11-13T14:00:00Z")   # an exact time before registration
    assert edge["eligible"]


def test_record_holds_every_timing_fact():
    r = go("2026-11-13T15:00:00Z", horizon=5)
    for k in ("spec_hash", "registration_utc", "sources", "data_cutoff_utc", "horizon_sessions", "execution_lag",
              "first_eligible_observation", "first_observation_close_utc", "first_window_end", "eligible"):
        assert k in r
    assert r["first_window_end"] == "2026-11-20"


# ---- the API record and input checks

def test_merge_time_comes_from_the_api_and_unmerged_is_refused():
    pr = {"merged": True, "merged_at": "2026-11-13T15:00:00Z", "merge_commit_sha": "c" * 40}
    assert T.merged_at_from_api(pr) == (t("2026-11-13T15:00:00Z"), "c" * 40)
    with pytest.raises(T.TimingError, match="not merged"):
        T.merged_at_from_api({"merged": False, "merged_at": None, "merge_commit_sha": None})
    with pytest.raises(T.TimingError, match="not the commit"):
        T.merged_at_from_api(pr, manifest_commit="d" * 40)
    with pytest.raises(T.TimingError, match="zone"):
        T.parse_time("2026-11-13T15:00:00")


def test_timing_fields_are_validated():
    assert T.validate_timing({}) == [f"timing.{k} is required" for k in T.TIMING_FIELDS]
    bad = tim(cal="lse")
    bad["horizon_sessions"] = 0
    bad["execution_lag"] = {"minutes": -1}
    errs = T.validate_timing(bad)
    assert any("calendar" in e for e in errs) and any("horizon" in e for e in errs) and any("minutes" in e for e in errs)
