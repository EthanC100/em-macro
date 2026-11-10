"""Config change C07 (approved by Ethan 2026-11-10, docs/config_changes.md): no 50% calls, a wider search when the
C06 two-position minimum binds, a time anchor for every review, and deferrals that count toward the minimum only
where the instrument's market is closed (and must open at the next session).

Every rejection test here fails on the code before C07 (which accepted these proposals) and passes after."""
import json
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from ledger import janus as J
from test_janus import SOURCES_READ, pos, review
from test_janus_c06 import EVENT, SR, marks

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
T = datetime(2026, 11, 10, 23, 7, tzinfo=UTC)               # Tuesday: the first daily review under C07
CPI = {"event": "US October CPI (BLS)", "time_utc": "2026-11-10T13:30:00Z", "occurred": True}
ANCHOR = {"now_utc": "2026-11-10T23:07:00Z", "events": [CPI]}
TWO = [pos(instrument="US10Y", stop=5.10, risk_pct=0.25), pos(instrument="DE10Y", stop=3.50, risk_pct=0.25)]


def cand(inst, direction="long", outcome="not_opened", opposition="none", **over):
    return {"instrument": inst, "direction": direction, "probability": 56, "market_probability": 50,
            "outcome": outcome, "opposition": opposition, "reason": "ranked on edge over the market probability", **over}


CANDS = [cand("US10Y", outcome="opened", opposition="kept"), cand("DE10Y", outcome="opened", opposition="kept"),
         cand("EUR"), cand("GOLD"), cand("WTI", "short")]


def c07(**over):
    return review(**{"new_positions": TWO, "sources_read": SR, "below_budget": EVENT, "time_anchor": ANCHOR,
                     "candidates": CANDS, **over})


def run(tmp_path, ans, now=T, mk=None, name="r.jsonl"):
    return J.apply_proposal(ans, now=now, path=tmp_path / name, marks_rows=marks() if mk is None else mk)


def errs_with(res, text):
    return [e for e in res["errors"] if text in e]


def test_a_compliant_review_passes_and_records_its_anchor_and_candidates(tmp_path):
    res = run(tmp_path, c07())
    assert res["ok"], res["errors"]
    rec = [r for r in J.load(tmp_path / "r.jsonl") if r["type"] == "run"][-1]
    assert rec["time_anchor"] == ANCHOR and rec["candidates"] == CANDS


# ----------------------------------------------------------------------------- rule 1: no 50% calls
@pytest.mark.parametrize("p", [50, 50.0, "50"])
def test_an_opened_position_at_50_percent_is_rejected(tmp_path, p):
    new = [TWO[0], {**TWO[1], "probability": p}]
    cands = [CANDS[0], {**CANDS[1], "probability": 50}] + CANDS[2:]
    res = run(tmp_path, c07(new_positions=new, candidates=cands))
    assert not res["ok"] and errs_with(res, "new position 2 (DE10Y): probability 50 is not a call (C07)"), res["errors"]


def test_near_50_is_a_call_and_a_50_candidate_not_opened_is_fine(tmp_path):
    new = [{**TWO[0], "probability": 49.5}, {**TWO[1], "probability": 51}]
    res = run(tmp_path, c07(new_positions=new, candidates=CANDS[:2] + [{**CANDS[2], "probability": 50}] + CANDS[3:]))
    assert res["ok"], res["errors"]


def test_a_deferred_idea_at_50_percent_is_rejected(tmp_path):
    sat = datetime(2026, 11, 14, 23, 7, tzinfo=UTC)
    ideas = [{"instrument": i, "direction": "long", "risk_pct": 1.5, "probability": p, "market_probability": 50,
              "thesis": "Enter at Monday's mark."} for i, p in (("US10Y", 50), ("DE10Y", 57))]
    res = run(tmp_path, c07(new_positions=[], no_trade_reasoning="Weekend.", below_budget=None, deferred_ideas=ideas,
                            time_anchor={**ANCHOR, "now_utc": sat.isoformat()},
                            candidates=[cand(d["instrument"], outcome="deferred") for d in ideas] + CANDS[2:]),
              now=sat, mk=marks("2026-11-13"))
    assert not res["ok"] and errs_with(res, "deferred idea 1 (US10Y): probability 50 is not a call"), res["errors"]


# ----------------------------------------------------------------------------- rule 2: wider search
@pytest.mark.parametrize("cands, expect", [
    (None, "list at least 5 candidates across at least 2 asset classes"),
    (CANDS[:4], "candidates name 4 distinct instrument(s); at least 5 are required"),
    (CANDS[:2] + [cand("GB10Y"), cand("JP10Y"), cand("FR-DE")], "candidates span 1 asset class(es) (rates)"),
    (CANDS[:2] + [cand("EUR"), cand("EUR", "short"), cand("GOLD")], "4 distinct instrument(s)"),
    (CANDS[1:] + [cand("JPY")], "every opened position as outcome 'opened': long US10Y is missing"),
    (CANDS[:4] + [cand("CAD", outcome="opened", opposition="kept")], "candidate 5 (CAD): outcome opened, but"),
    (CANDS[:4] + [cand("PLATINUM")], "candidate 5 (PLATINUM): not in the universe"),
    (CANDS[:4] + [cand("CAD", reason="")], "reason is required"),
    (CANDS[:4] + [cand("CAD", outcome="maybe")], "outcome must be one of"),
    ([{**CANDS[0], "opposition": "none"}] + CANDS[1:], "an opened candidate went through The Opposition"),
])
def test_when_the_minimum_binds_the_review_lists_5_candidates_across_2_classes(tmp_path, cands, expect):
    res = run(tmp_path, c07(candidates=cands))
    assert not res["ok"] and errs_with(res, expect), res["errors"]


def test_the_minimum_binds_only_when_the_review_brings_the_book_to_exactly_two(tmp_path):
    three = TWO + [pos(instrument="GB10Y", stop=5.40, risk_pct=0.25)]
    res = run(tmp_path, c07(new_positions=three, candidates=None), name="three.jsonl")
    assert res["ok"], res["errors"]                                  # three positions: not the minimum
    assert run(tmp_path, c07())["ok"]
    held = c07(new_positions=[], no_trade_reasoning="Both views intact.", candidates=None,
               reviews=[{"id": "J001", "action": "hold", "reasoning": "on track"},
                        {"id": "J002", "action": "hold", "reasoning": "on track"}])
    res = run(tmp_path, held)
    assert res["ok"], res["errors"]                                  # holding two: nothing added to meet it
    one_more = c07(new_positions=[pos(instrument="GB10Y", stop=5.40, risk_pct=0.25)], candidates=None,
                   reviews=[{"id": "J001", "action": "close", "reasoning": "the trigger fired"},
                            {"id": "J002", "action": "hold", "reasoning": "on track"}])
    res = run(tmp_path, one_more)
    assert not res["ok"] and errs_with(res, "the C06 two-position minimum binds"), res["errors"]


def test_a_candidate_dropped_after_the_opposition_is_reopened_only_with_a_reason(tmp_path):
    dropped = {**CANDS[1], "opposition": "dropped"}
    res = run(tmp_path, c07(candidates=[CANDS[0], dropped] + CANDS[2:]))
    assert not res["ok"] and errs_with(res, "candidate 2 (DE10Y): dropped after The Opposition and reopened"), res["errors"]
    vague = {**dropped, "reopen_reason": "It is still the best of the rest of the list, so it is reopened."}
    res = run(tmp_path, c07(candidates=[CANDS[0], vague] + CANDS[2:]))
    assert not res["ok"] and errs_with(res, "it does not name EUR, GOLD, WTI"), res["errors"]
    why = {**dropped, "reopen_reason": "EUR needs the ECB to move first, GOLD's edge is under 3 points and WTI's stop is "
                                       "inside a normal day's range, so none of them beats a small DE10Y long."}
    res = run(tmp_path, c07(candidates=[CANDS[0], why] + CANDS[2:]))
    assert res["ok"], res["errors"]


# ----------------------------------------------------------------------------- rule 3: time anchor
def anchor(**over):
    return {**ANCHOR, **over}


@pytest.mark.parametrize("ta, expect", [
    (None, "time_anchor (C07): required"),
    (anchor(now_utc="2026-11-10 23:07"), "now_utc must be the review's current UTC time"),
    (anchor(now_utc="2026-11-10T18:07:00-05:00"), "now_utc must be the review's current UTC time"),
    (anchor(now_utc="2026-11-10T18:00:00Z"), "is not the time of this review"),
    (anchor(now_utc="2026-11-11T09:00:00Z"), "is not the time of this review"),
    (anchor(events=[]), "names 10 Nov, but time_anchor.events has no event on that date"),
    (anchor(events=[{**CPI, "event": "US October data"}]), "below_budget.condition cites CPI, but no event"),
    (anchor(events=[{**CPI, "occurred": False}]), "occurred is false, but at now_utc"),
    (anchor(events=[CPI, {"event": "FOMC decision", "date": "2026-12-09", "occurred": True}]), "dated in the future"),
    (anchor(events=[{**CPI, "time_utc": None, "date": "2026-11-10"}]), "on the review's own UTC date"),
    (anchor(events=[{**CPI, "occurred": "yes"}]), "occurred must be true or false"),
])
def test_every_review_records_its_utc_time_and_each_cited_event(tmp_path, ta, expect):
    res = run(tmp_path, c07(time_anchor=ta))
    assert not res["ok"] and errs_with(res, expect), res["errors"]


def test_every_cited_date_and_scheduled_event_must_be_anchored(tmp_path):
    new = [{**TWO[0], "thesis": "Payrolls were soft and the 8-9 Dec FOMC should lean dovish. Yields drift lower."}, TWO[1]]
    res = run(tmp_path, c07(new_positions=new))
    assert errs_with(res, "new position 1 (US10Y) thesis names 9 Dec"), res["errors"]
    assert errs_with(res, "new position 1 (US10Y) thesis cites payrolls"), res["errors"]
    assert errs_with(res, "new position 1 (US10Y) thesis cites FOMC")
    ok = anchor(events=[CPI, {"event": "FOMC decision", "date": "2026-12-09", "occurred": False},
                        {"event": "US October payrolls (BLS)", "time_utc": "2026-11-06T13:30:00Z", "occurred": True}])
    assert run(tmp_path, c07(new_positions=new, time_anchor=ok))["ok"]


BEFORE_CPI = datetime(2026, 11, 10, 10, 30, 9, tzinfo=UTC)       # 10:30 UTC: CPI is due at 13:30 UTC (08:30 ET)
EARLY = {"now_utc": BEFORE_CPI.isoformat(), "events": [{**CPI, "occurred": False}]}


@pytest.mark.parametrize("reasoning", [
    "The October CPI released at 08:30 ET on 10 Nov drives every rates idea.",
    "CPI was released on 10 Nov and came in soft.",
    "The 10 Nov CPI print showed core easing, so size up.",
    "October CPI has been published and surprised lower.",
])
def test_an_event_dated_in_the_future_cannot_be_described_as_released(tmp_path, reasoning):
    res = run(tmp_path, c07(time_anchor=EARLY, below_budget={**EVENT, "reasoning": reasoning}), now=BEFORE_CPI)
    assert not res["ok"] and errs_with(res, "describes US October CPI (BLS) as"), res["errors"]
    assert errs_with(res, "an event dated in the future cannot be described as released")


@pytest.mark.parametrize("reasoning", [
    "US CPI is due to be released at 13:30 UTC on 10 Nov; size up once the print is out.",
    "The October CPI, which is released at 08:30 ET on 10 Nov, has not been released yet.",
    "Wait until CPI is published on 10 Nov before adding risk.",
    "September CPI came in hot, and October CPI is scheduled for 10 Nov.",
])
def test_a_future_event_may_be_described_as_due(tmp_path, reasoning):
    ta = {**EARLY, "events": EARLY["events"] + [{"event": "US September CPI (BLS)", "date": "2026-10-15",
                                                  "occurred": True}]}
    res = run(tmp_path, c07(time_anchor=ta, below_budget={**EVENT, "reasoning": reasoning}), now=BEFORE_CPI)
    assert res["ok"], res["errors"]


# ----------------------------------------------------------------------------- the 10 Nov 10:30 UTC review (J001, J002)
def _records_until(seq):
    return [json.loads(x) for x in (ROOT / "data/janus/records.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip() and json.loads(x)["seq"] <= seq]


def _10_nov_proposal():
    """The proposal behind records 208-212 (J001, J002), rebuilt from the chain; the records are not edited."""
    recs = {r["seq"]: r for r in _records_until(212)}
    run_, opens, opps = recs[208], [recs[209], recs[211]], {recs[210]["position_id"]: recs[210],
                                                           recs[212]["position_id"]: recs[212]}
    keep = ("instrument", "direction", "risk_pct", "stop", "horizon", "probability", "thesis", "change_mind", "sources",
            "market_probability", "market_source", "market_basis")
    return {"session": "daily_review", "model": run_["model"], "market_summary": run_["market_summary"], "reviews": [],
            "new_positions": [{**{k: o[k] for k in keep}, "opposition": {**opps[o["position_id"]]["opposition"],
                                                                         "model": opps[o["position_id"]]["model"]}}
                              for o in opens],
            "no_trade_reasoning": "", "sources_read": run_["sources_read"], "below_budget": run_["below_budget"]}


def test_the_10_nov_review_that_opened_j001_and_j002_is_rejected_under_c07(tmp_path):
    recs = _records_until(212)
    assert J.verify(recs)["ok"] and [recs[208]["probability"], recs[210]["probability"]] == [50.0, 50.0]
    path = tmp_path / "r.jsonl"
    path.write_text("".join(json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
                            for r in recs[:207]))
    ans = _10_nov_proposal()
    mk = marks()
    res = J.apply_proposal(ans, now=BEFORE_CPI, path=path, marks_rows=mk, dry_run=True)
    assert not res["ok"]
    assert errs_with(res, "new position 1 (US10Y): probability 50 is not a call")
    assert errs_with(res, "new position 2 (GB10Y): probability 50 is not a call")
    assert errs_with(res, "list at least 5 candidates across at least 2 asset classes")
    assert errs_with(res, "time_anchor (C07): required")
    # with a truthful anchor (CPI due at 13:30 UTC, not yet out at 10:30 UTC), the reason's "released" is caught
    res = J.apply_proposal({**ans, "time_anchor": EARLY}, now=BEFORE_CPI, path=path, marks_rows=mk, dry_run=True)
    assert errs_with(res, "below_budget.reasoning describes US October CPI (BLS) as 'released'"), res["errors"]
    # both positions are rates: even five rates candidates would not do
    rates = [cand(i, outcome=("opened" if i in ("US10Y", "GB10Y") else "not_opened"),
                  opposition=("dropped" if i in ("US10Y", "GB10Y") else "none"))
             for i in ("US10Y", "GB10Y", "DE10Y", "JP10Y", "FR-DE")]
    res = J.apply_proposal({**ans, "time_anchor": EARLY, "candidates": rates}, now=BEFORE_CPI, path=path,
                           marks_rows=mk, dry_run=True)
    assert errs_with(res, "candidates span 1 asset class(es) (rates)")
    assert errs_with(res, "candidate 1 (US10Y): dropped after The Opposition and reopened")
    assert path.read_text().count("\n") == 207                      # dry runs write nothing


# ----------------------------------------------------------------------------- rule 4: deferrals
WED = datetime(2026, 11, 11, 23, 7, tzinfo=UTC)                  # a weekday market holiday (US Veterans Day)
SIFMA = "https://www.sifma.org/resources/general/holiday-schedule/"
SR_H = SR + [{"title": "SIFMA holiday schedule", "url": SIFMA, "driver": "data"}]


def idea(inst, **over):
    return {"instrument": inst, "direction": "long", "risk_pct": 0.5, "probability": 56, "market_probability": 50,
            "thesis": "Enter at the next session's mark.", **over}


def holiday(**over):
    return c07(**{"market_holiday": "US Veterans Day", "sources_read": SR_H, "below_budget": None,
                  "time_anchor": anchor(now_utc=WED.isoformat()), **over})


CLOSED = {"holiday": "Veterans Day (US bond market closed)", "calendar_url": SIFMA}


def test_on_a_weekday_a_deferred_idea_counts_only_if_its_market_is_closed(tmp_path):
    mk = marks("2026-11-10")
    # FX trades on Veterans Day: a deferred EUR idea does not count, so one opened position leaves the book at 1
    res = run(tmp_path, holiday(new_positions=[TWO[0]], deferred_ideas=[idea("EUR", risk_pct=2.0)],
                                candidates=[CANDS[0], cand("EUR", outcome="deferred")] + CANDS[2:]), now=WED, mk=mk)
    assert not res["ok"] and errs_with(res, "C06 requires at least 2"), res["errors"]
    # a closed US Treasury market with its calendar counts
    res = run(tmp_path, holiday(new_positions=[pos(instrument="EUR", stop=1.10, risk_pct=2.0)],
                                deferred_ideas=[idea("US10Y", risk_pct=1.0, market_closed=CLOSED)],
                                candidates=[cand("EUR", outcome="opened", opposition="kept"),
                                            cand("US10Y", outcome="deferred")] + [cand(i) for i in ("GOLD", "WTI", "JPY")]),
              now=WED, mk=mk, name="ok.jsonl")
    assert res["ok"], res["errors"]


@pytest.mark.parametrize("mc, sr, expect", [
    (None, SR_H, "C06 requires at least 2"),
    ({"holiday": "Veterans Day", "calendar_url": "https://www.timeanddate.com/holidays/us/veterans-day"},
     SR_H + [{"title": "t", "url": "https://www.timeanddate.com/holidays/us/veterans-day"}],
     "market_closed.calendar_url must be the exchange's or an official holiday calendar"),
    (CLOSED, SR, "must also be listed in sources_read"),
    ({"calendar_url": SIFMA}, SR_H, "market_closed.holiday is required"),
])
def test_a_weekday_closure_must_be_named_and_cited(tmp_path, mc, sr, expect):
    ans = holiday(sources_read=sr, new_positions=[pos(instrument="EUR", stop=1.10, risk_pct=2.0)],
                  deferred_ideas=[idea("US10Y", **({"market_closed": mc} if mc else {}))],
                  candidates=[cand("EUR", outcome="opened", opposition="kept"),
                              cand("US10Y", outcome="deferred")] + [cand(i) for i in ("GOLD", "WTI", "JPY")])
    res = run(tmp_path, ans, now=WED, mk=marks("2026-11-10"))
    assert not res["ok"] and errs_with(res, expect), res["errors"]


def test_fx_markets_are_open_on_weekdays():
    assert J.market_closed(idea("EUR"), date(2026, 11, 11), {}) == (False, None)
    assert J.market_closed(idea("EUR"), date(2026, 12, 25), {})[0]
    assert "FX trades every weekday" in J.market_closed(idea("EUR", market_closed=CLOSED), date(2026, 11, 11), {})[1]
    assert J.market_closed(idea("WTI"), date(2026, 11, 14), {}) == (True, None)        # Saturday: every market
    assert J.market_calendar(SIFMA) and J.market_calendar("https://www.cmegroup.com/trading-hours.html")
    assert not J.market_calendar("https://www.timeanddate.com/holidays/us/")


SAT = datetime(2026, 11, 14, 23, 7, tzinfo=UTC)
SUN, MON = SAT + timedelta(days=1), SAT + timedelta(days=2)


def weekend(now, **over):
    return c07(**{"new_positions": [], "no_trade_reasoning": "Weekend: entries deferred to Monday.", "below_budget": None,
                  "deferred_ideas": [idea("US10Y", risk_pct=1.5), idea("EUR", risk_pct=1.5)],
                  "candidates": [cand("US10Y", outcome="deferred"), cand("EUR", outcome="deferred"), cand("DE10Y"),
                                 cand("GOLD"), cand("WTI", "short")],
                  "time_anchor": anchor(now_utc=now.isoformat()), **over})


def test_a_deferred_idea_must_open_at_the_next_session(tmp_path):
    mk = marks("2026-11-13")
    assert run(tmp_path, weekend(SAT), now=SAT, mk=mk)["ok"]
    # Monday: the review that does not open them is rejected
    mon = c07(time_anchor=anchor(now_utc=MON.isoformat()))
    res = run(tmp_path, mon, now=MON, mk=mk)
    assert not res["ok"] and errs_with(res, "deferred idea long EUR from the 2026-11-14 review must open at the next "
                                            "session"), res["errors"]
    assert not errs_with(res, "deferred idea long US10Y")            # this review opens US10Y (in TWO)
    # opening both (with The Opposition) passes
    both = [pos(instrument="US10Y", stop=5.10, risk_pct=1.5), pos(instrument="EUR", stop=1.10, risk_pct=1.5)]
    res = run(tmp_path, c07(new_positions=both, below_budget=None, time_anchor=anchor(now_utc=MON.isoformat()),
                            candidates=[cand("US10Y", outcome="opened", opposition="kept"),
                                        cand("EUR", outcome="opened", opposition="kept"),
                                        cand("DE10Y"), cand("GOLD"), cand("WTI", "short")]), now=MON, mk=mk)
    assert res["ok"], res["errors"]


def test_a_weekend_review_carries_deferred_ideas_forward(tmp_path):
    mk = marks("2026-11-13")
    assert run(tmp_path, weekend(SAT), now=SAT, mk=mk)["ok"]
    dropped = weekend(SUN, deferred_ideas=[idea("US10Y", risk_pct=1.5), idea("GBP", risk_pct=1.5)],
                      candidates=[cand("US10Y", outcome="deferred"), cand("GBP", outcome="deferred"), cand("DE10Y"),
                                  cand("GOLD"), cand("WTI", "short")])
    res = run(tmp_path, dropped, now=SUN, mk=mk)
    assert not res["ok"] and errs_with(res, "deferred idea long EUR from the 2026-11-14 review"), res["errors"]
    assert run(tmp_path, weekend(SUN), now=SUN, mk=mk)["ok"]


def test_deferrals_before_c07_are_not_followed_up(tmp_path):
    """A deferral recorded before C07 (7 Nov) is not held to the next-session rule (no record is re-judged)."""
    path = tmp_path / "r.jsonl"
    J.append(J.load(path), {"type": "run", "session": "daily_review", "date": "2026-11-07", "status": "ok",
                            "deferred_ideas": [idea("CHF")], "model": "m", "decided_at": "2026-11-07T23:07:00+00:00"},
             path)
    assert run(tmp_path, c07())["ok"]


# ----------------------------------------------------------------------------- failed reviews and public text
def test_a_c07_rejection_writes_the_failed_record_with_its_utc_time_and_withholds_futures_details(tmp_path):
    new = [{**TWO[0], "probability": 50}, pos(instrument="WTI", stop=60.0, risk_pct=0.25, probability=50)]
    res = run(tmp_path, c07(new_positions=new, candidates=CANDS[:1] + [cand("WTI", outcome="opened", opposition="kept")]
                            + CANDS[2:4] + [cand("CAD")]))
    assert not res["ok"] and res["failed_record"] == 1
    rec = J.load(tmp_path / "r.jsonl")[0]
    assert (rec["status"], rec["now_utc"]) == ("failed", ANCHOR["now_utc"])
    assert any("new position 1 (US10Y): probability 50 is not a call" in e for e in rec["errors"])
    wti = [e for e in rec["errors"] if "(WTI)" in e]
    assert wti and all("details not recorded" in e for e in wti)
    assert J.review_status(J.load(tmp_path / "r.jsonl"), date(2026, 11, 10))["status"] == "failed"


def test_c07_rules_apply_from_c07_only():
    """A 9 Nov review (before C07) with a 50% call and no time anchor still passes: earlier behaviour is unchanged."""
    res = J.apply_proposal(review(sources_read=SR, new_positions=[pos(probability=50)]),
                           now=datetime(2026, 11, 9, 23, 7, tzinfo=UTC), path=None, marks_rows=marks("2026-11-06"))
    assert res["ok"], res["errors"]


def test_c07_is_recorded_in_the_config_changes_and_the_runbooks():
    assert J.C07_FROM == date(2026, 11, 10) and J.NO_VIEW_PROBABILITY == 50.0
    assert (J.MIN_CANDIDATES, J.MIN_CANDIDATE_CLASSES, J.MIN_POSITIONS) == (5, 2, 2)
    doc = (ROOT / "docs/config_changes.md").read_text(encoding="utf-8")
    assert "| C07 | 2026-11-10 |" in doc and "## C07" in doc and "Approved by Ethan on 2026-11-10" in doc
    for f in ("docs/janus/daily_review.md", "docs/janus/quick_check.md"):
        assert "C07" in (ROOT / f).read_text(encoding="utf-8")
    rb = (ROOT / "docs/janus/daily_review.md").read_text(encoding="utf-8")
    example = json.loads(rb.split("`/tmp/janus_review.json` (C07 format):\n\n```json\n", 1)[1].split("\n```", 1)[0])
    assert {"time_anchor", "candidates"} <= set(example) and example["new_positions"][0]["probability"] != 50


def test_the_runbook_example_passes_the_cli(tmp_path):
    """The C07-format example in docs/janus/daily_review.md, with its placeholders filled and the blocks that do not
    apply left out, passes: the book holds J001, the example opens a second position, so the minimum binds."""
    rb = (ROOT / "docs/janus/daily_review.md").read_text(encoding="utf-8")
    ex = json.loads(rb.split("`/tmp/janus_review.json` (C07 format):\n\n```json\n", 1)[1].split("\n```", 1)[0])
    for k in ("data_failure", "deferred_ideas", "market_holiday"):
        ex.pop(k)
    ex.update(sources_read=SR, model="claude-opus-5-5")
    ex["new_positions"][0]["sources"] = [{"title": "FOMC statement", "url": "https://www.federalreserve.gov/x"}]
    ex["below_budget"]["reasoning"] = "Size up after the print is digested."
    ex["reviews"][0]["reasoning"] = "On track."
    assert J.apply_proposal(review(sources_read=SR, new_positions=[pos(instrument="DE10Y", stop=3.50, risk_pct=0.25)]),
                            now=datetime(2026, 11, 9, 23, 7, tzinfo=UTC), path=tmp_path / "r.jsonl",
                            marks_rows=marks("2026-11-06"))["ok"]
    res = J.apply_proposal(ex, now=T, path=tmp_path / "r.jsonl", marks_rows=marks())
    assert res["ok"], res["errors"]
