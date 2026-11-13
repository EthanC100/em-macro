"""Freeze validity, separate from authorisation (criteria O-06 to O-10).

Ethan's merge of a manifest pull request **authorises** a freeze. It does not certify timing. Timing is checked
here, mechanically, for every prediction:

    registration time  R = the later of GitHub's server-side merge time (the API's ``merged_at``) and a verified
                           external witness time (OpenTimestamps or equivalent). If either source is honest, the
                           spec existed by R. Without a verified witness the registration is ``provisional``.
    first eligible     O1 = the first market observation (a session close on the family's calendar, in the
    observation             market's time zone) strictly after R + the execution lag in time, then moved forward by
                           the execution lag in sessions.
    prospective        at R the outcome window had not begun (the close of its first observation is after R) and
                       nothing in it was observable (that close's value was published after R).

The outcome window of a prediction starts at its first observation: the position is entered at that close and the
first recorded return is the next session's. A prediction that declares an earlier first observation than O1, whose
data cutoff is not before R, or whose data cutoff falls inside the outcome window, is **ineligible**: it is recorded
and tracked with evidential weight 0, never dropped.

Calendars are rule-based (weekends and the holidays below). They are deliberately simple and conservative; a
missing special closure can only make an observation date that does not exist, which the runner then records as
missed, never as an outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

UTC = timezone.utc


class TimingError(ValueError):
    pass


# ---------------------------------------------------------------- holidays

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th given weekday (0 = Monday) of a month; n = -1 for the last."""
    if n > 0:
        d = date(year, month, 1)
        d += timedelta(days=(weekday - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _observed(d: date, saturday_to_friday: bool) -> date | None:
    if d.weekday() == 6:
        return d + timedelta(days=1)
    if d.weekday() == 5:
        return d - timedelta(days=1) if saturday_to_friday else None
    return d


@lru_cache(maxsize=None)
def us_federal_holidays(year: int) -> frozenset:
    """Federal Reserve holidays (the H.10 exchange-rate calendar): a Sunday holiday is observed on Monday; on a
    Saturday holiday the Reserve Banks are open the Friday before, so nothing is observed."""
    raw = [date(year, 1, 1), _nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3), _nth_weekday(year, 5, 0, -1),
           date(year, 7, 4), _nth_weekday(year, 9, 0, 1), _nth_weekday(year, 10, 0, 2), date(year, 11, 11),
           _nth_weekday(year, 11, 3, 4), date(year, 12, 25)]
    if year >= 2021:
        raw.append(date(year, 6, 19))
    return frozenset(o for o in (_observed(d, False) for d in raw) if o is not None)


@lru_cache(maxsize=None)
def nyse_holidays(year: int) -> frozenset:
    """NYSE full-day holidays by rule (special closures are not modelled)."""
    out = set()
    ny = _observed(date(year, 1, 1), saturday_to_friday=False)      # a Saturday New Year is not moved to Friday
    if ny:
        out.add(ny)
    out |= {_nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3), easter(year) - timedelta(days=2),
            _nth_weekday(year, 5, 0, -1), _nth_weekday(year, 9, 0, 1), _nth_weekday(year, 11, 3, 4)}
    for d in ([date(year, 6, 19)] if year >= 2022 else []) + [date(year, 7, 4), date(year, 12, 25)]:
        o = _observed(d, saturday_to_friday=True)
        if o:
            out.add(o)
    return frozenset(out)


def no_holidays(year: int) -> frozenset:
    return frozenset()


# ---------------------------------------------------------------- calendars

@dataclass(frozen=True)
class Calendar:
    """Sessions (weekdays that are not holidays) closing at ``close`` in ``tz``. The value of a session's close is
    published ``publish_sessions`` sessions later at ``publish_time`` local time (0 sessions and the close time:
    published at the close)."""
    name: str
    tz: str
    close: time
    holidays: object                 # year -> frozenset of dates
    publish_sessions: int = 0
    publish_time: time | None = None

    def is_session(self, d: date) -> bool:
        return d.weekday() < 5 and d not in self.holidays(d.year)

    def close_utc(self, d: date) -> datetime:
        return datetime.combine(d, self.close, tzinfo=ZoneInfo(self.tz)).astimezone(UTC)

    def next_session(self, d: date) -> date:
        d += timedelta(days=1)
        while not self.is_session(d):
            d += timedelta(days=1)
        return d

    def prev_session(self, d: date) -> date:
        d -= timedelta(days=1)
        while not self.is_session(d):
            d -= timedelta(days=1)
        return d

    def published_utc(self, d: date) -> datetime:
        p = d
        for _ in range(self.publish_sessions):
            p = self.next_session(p)
        t = self.publish_time or self.close
        out = datetime.combine(p, t, tzinfo=ZoneInfo(self.tz)).astimezone(UTC)
        return max(out, self.close_utc(d))

    def first_close_after(self, t: datetime) -> date:
        """The first session whose close is strictly after ``t`` (an aware datetime)."""
        if t.tzinfo is None:
            raise TimingError("times must carry a time zone")
        d = t.astimezone(ZoneInfo(self.tz)).date() - timedelta(days=1)
        for _ in range(30):
            if self.is_session(d) and self.close_utc(d) > t:
                return d
            d += timedelta(days=1)
        raise TimingError("no session within 30 days")      # pragma: no cover

    def sessions(self, start: date, end: date) -> list[date]:
        out, d = [], start
        while d <= end:
            if self.is_session(d):
                out.append(d)
            d += timedelta(days=1)
        return out

    def advance(self, d: date, n: int) -> date:
        for _ in range(n):
            d = self.next_session(d)
        return d


CALENDARS = {
    # H.10 noon buying rates (FRED DEX*): the Federal Reserve's calendar; the series for a day is out the next
    # business day in the afternoon. FX "close" is taken as 17:00 New York, the market convention.
    "us_fed_fx": Calendar("us_fed_fx", "America/New_York", time(17, 0), us_federal_holidays, 1, time(16, 15)),
    "nyse": Calendar("nyse", "America/New_York", time(16, 0), nyse_holidays, 0, time(16, 0)),
    # synthetic data used by tests and the end-to-end proof: weekdays, US federal holidays, published at the close
    "synthetic": Calendar("synthetic", "America/New_York", time(17, 0), us_federal_holidays, 0, None),
}


def calendar(name: str) -> Calendar:
    try:
        return CALENDARS[name]
    except KeyError:
        raise TimingError(f"unknown calendar {name}; known: {sorted(CALENDARS)}") from None


# ---------------------------------------------------------------- registration

def parse_time(s: str) -> datetime:
    """An ISO 8601 time with a zone (``Z`` or an offset). A naive time is refused."""
    t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise TimingError(f"{s}: a time must carry its zone")
    return t.astimezone(UTC)


def iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def merged_at_from_api(pr: dict, manifest_commit: str | None = None) -> tuple[datetime, str]:
    """(merge time, merge commit) from the JSON of ``GET /repos/{owner}/{repo}/pulls/{n}``. Refuses an unmerged
    pull request. The time is GitHub's server-side record, not a commit date (which anyone can set)."""
    if not pr.get("merged") or not pr.get("merged_at") or not pr.get("merge_commit_sha"):
        raise TimingError("the pull request is not merged: nothing is registered")
    if manifest_commit is not None and pr["merge_commit_sha"] != manifest_commit:
        raise TimingError("the merge commit is not the commit that holds the manifest")
    return parse_time(pr["merged_at"]), pr["merge_commit_sha"]


@dataclass(frozen=True)
class Witness:
    """An external timestamp of the manifest hash: ``attested`` is the latest time the witness says the hash
    existed by (for OpenTimestamps, the Bitcoin block time once the proof is complete)."""
    kind: str
    digest: str
    attested: datetime | None
    verified: bool

    def payload(self) -> dict:
        return {"kind": self.kind, "digest": self.digest, "verified": self.verified,
                "attested_utc": iso(self.attested) if self.attested else None}


def registration_time(merged: datetime, witness: Witness | None, manifest_hash: str) -> tuple[datetime, str]:
    """(R, status). ``witnessed``: R is the later of the two sources. ``provisional``: no verified witness of this
    manifest yet; R is the merge time and the record is re-assessed when the witness arrives."""
    if witness is None or not witness.verified or witness.attested is None:
        return merged, "provisional"
    if witness.digest != manifest_hash:
        raise TimingError("the witness is of a different hash than the manifest")
    return max(merged, witness.attested), "witnessed"


def _cutoff(value, cal: Calendar) -> datetime:
    """A data cutoff as a time: an ISO time, or a date meaning 'through that day', i.e. the end of that day in the
    market's zone (the conservative reading)."""
    s = str(value)
    if "T" in s:
        return parse_time(s)
    d = date.fromisoformat(s)
    return datetime.combine(d + timedelta(days=1), time(0, 0), tzinfo=ZoneInfo(cal.tz)).astimezone(UTC)


TIMING_FIELDS = ("calendar", "horizon_sessions", "execution_lag", "data_cutoff")


def validate_timing(t: dict) -> list[str]:
    errs = [f"timing.{k} is required" for k in TIMING_FIELDS if k not in (t or {})]
    if errs:
        return errs
    if t["calendar"] not in CALENDARS:
        errs.append(f"timing.calendar must be one of {sorted(CALENDARS)}")
    h = t["horizon_sessions"]
    if isinstance(h, bool) or not isinstance(h, int) or h < 1:
        errs.append("timing.horizon_sessions must be a whole number of sessions, at least 1")
    lag = t["execution_lag"]
    if not isinstance(lag, dict) or set(lag) - {"minutes", "sessions"}:
        errs.append("timing.execution_lag is {minutes, sessions}")
    else:
        for k in ("minutes", "sessions"):
            v = lag.get(k, 0)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                errs.append(f"timing.execution_lag.{k} must be a whole number, 0 or more")
    try:
        _cutoff(t["data_cutoff"], CALENDARS.get(t["calendar"], CALENDARS["synthetic"]))
    except (ValueError, TimingError):
        errs.append("timing.data_cutoff must be a date or an ISO time with its zone")
    if t.get("declared_first_observation") is not None:
        try:
            date.fromisoformat(str(t["declared_first_observation"]))
        except ValueError:
            errs.append("timing.declared_first_observation must be a date")
    return errs


def assess(*, prediction_id: str, spec_hash: str, manifest_hash: str, merged: datetime, merge_commit: str,
           witness: Witness | None, timing: dict) -> dict:
    """The registration payload of one prediction: every timing fact and the eligibility verdict."""
    errs = validate_timing(timing)
    if errs:
        raise TimingError("; ".join(errs))
    cal = calendar(timing["calendar"])
    R, status = registration_time(merged, witness, manifest_hash)
    lag = timing["execution_lag"]
    lag_min, lag_ses = int(lag.get("minutes", 0)), int(lag.get("sessions", 0))
    o1 = cal.advance(cal.first_close_after(R + timedelta(minutes=lag_min)), lag_ses)
    declared = timing.get("declared_first_observation")
    start = date.fromisoformat(str(declared)) if declared is not None else o1
    cutoff = _cutoff(timing["data_cutoff"], cal)
    reasons = []
    if declared is not None and not cal.is_session(start):
        reasons.append("declared_first_observation_not_a_session")
    if cal.close_utc(start) <= R:
        # the window had begun; say whether the merge alone would have been in time (a late witness)
        reasons.append("witness_after_window_start" if cal.close_utc(start) > merged else "window_begun_at_registration")
    elif cal.published_utc(start) <= R:                        # pragma: no cover - publication is never before the close
        reasons.append("outcome_observable_at_registration")
    elif start < o1:
        reasons.append("first_observation_inside_execution_lag")
    if cutoff > R:
        reasons.append("data_cutoff_after_registration")
    if cutoff > cal.close_utc(start):
        reasons.append("data_cutoff_inside_outcome_window")
    end = cal.advance(start, int(timing["horizon_sessions"]))
    return {
        "prediction": prediction_id, "spec_hash": spec_hash, "manifest_hash": manifest_hash,
        "registration_utc": iso(R), "registration_status": status,
        "sources": {"github_merged_at": iso(merged), "merge_commit": merge_commit,
                    "witness": witness.payload() if witness else None},
        "calendar": cal.name, "data_cutoff_utc": iso(cutoff), "horizon_sessions": int(timing["horizon_sessions"]),
        "execution_lag": {"minutes": lag_min, "sessions": lag_ses},
        "declared_first_observation": str(declared) if declared is not None else None,
        "first_eligible_observation": o1.isoformat(), "first_observation": start.isoformat(),
        "first_window_end": end.isoformat(),
        "first_observation_close_utc": iso(cal.close_utc(start)),
        "first_observation_published_utc": iso(cal.published_utc(start)),
        "eligible": not reasons, "ineligible_reasons": reasons,
        # weight 1 only when eligible and witnessed; a provisional registration waits for its witness
        "evidential_weight": 1 if (not reasons and status == "witnessed") else 0,
    }
