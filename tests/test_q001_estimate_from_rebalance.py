"""Q001: the Algorithm's month-to-date estimate runs from the actual rebalance date, not the month start.

On 9 Nov 2026 the v1.0 estimate (books.json) was based on 2026-10-31 although the November positions were set only by
the late run of 4 Nov (results/systematic/rebalance_log.csv: "LATE by 1 day"), so it credited them with the 2, 3 and
4 Nov moves. Ethan's decision (2026-11-12): the estimate starts at the actual rebalance date and says so in its
label/note; the official month-end figure keeps the frozen full-month convention (v1.0's paper P&L, booked on the
3rd, credits the positions for the whole effective month) and is unchanged. The rules tested here:
1. base day = max(run date, month start - 1 day); the base mark is the last mark on or before the base day; the first
   P&L day is the first business day after it; carry is counted in calendar days from the base day;
2. a run date before the month starts is clamped to the previous month end (estimate points never precede the
   previous official month-end);
3. a weekend run date (Sunday 3 Jan 2027) uses the last mark on or before it, and P&L starts on Monday 4 Jan;
4. a re-run that restamps run_date with identical positions moves the base forward to the re-run's date (em_macro/
   rebalance.py keeps no first-run date); the estimate's note says so, and the base date is published;
5. which date each version uses: v1.0 the run_date column of results/systematic/positions.csv; v1.1 the same column
   of results/systematic_v1.1/positions.csv (stamped by its own step from the 3 Dec 2026 rebalance), else the run_date
   of its rebalance_log.csv row for the same effective month, else none: the full-month base (month start - 1 day),
   labelled as such. Git commit dates are never used (a re-commit is not a rebalance);
6. the official month-end points and index are unchanged.
Fixture positions, marks and policy rates in a temporary directory; never the live results/systematic*/ files or
data/ledger (Q025: tests pinned to live positions stop the monthly rebalance's commit)."""
import csv
from datetime import date

import pytest

from ledger import books as BK
from ledger import capacity as CAP
from ledger import pricing as PX

INST = "TSTFX"
REG = {INST: {"instrument": INST, "iso3": "XXX", "kind": "fx", "unit": "XXX per USD", "frequency": "daily",
              "book": "fx", "country": "Testland"}}
POLICY, FED = 10.0, 4.0                     # carry = (10 - 4)% a year
CARRY = (POLICY - FED) / 100.0
POS = [{"instrument": INST, "country": "Testland", "side": "long", "size_pct_of_capital": 50.0, "book": "fx",
        "effective_from": "2026-11"}]
POS_COLUMNS = ["as_of", "effective_from", "book", "instrument", "side", "size_pct_of_capital", "scheduled_date",
               "run_date"]


def _mark(d: str, v: float) -> dict:
    return {"date": d, "instrument": INST, "value": str(v), "unit": "XXX per USD", "frequency": "daily",
            "source": "fixture", "source_url": "", "fetched_at": f"{d}T22:00:00+00:00", "note": ""}


# a daily close every business day from 29 Oct 2026 to 8 Jan 2027, each one different
def _bdays_marks():
    out, v = [], 100.0
    for d in BK.bdays(date(2026, 10, 29), date(2027, 1, 8)):
        if d == date(2027, 1, 1):           # New Year's Day: no close
            continue
        v = round(v * (0.997 if d.toordinal() % 3 else 1.004), 6)
        out.append(_mark(d.isoformat(), v))
    return out


MARKS = _bdays_marks()


def _mb() -> BK.MarkBook:
    mb = BK.MarkBook(rows=[dict(r) for r in MARKS])
    mb.reg = dict(REG)
    return mb


def _val(d: str) -> float:
    return next(float(m["value"]) for m in MARKS if m["date"] == d)


def _expected(base_mark_day: str, base_day: date, d: date) -> float:
    """The estimate's per-day return (in % of capital) of the 50% long on day ``d``, from first principles."""
    r = PX.ret_long("fx_per_usd", _val(base_mark_day), _val(d.isoformat())) + CARRY * (d - base_day).days / 365.0
    return round(100 * 0.5 * r, 4)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    """Policy rates fixed; the books' and the capacity module's files under tmp_path; no git history."""
    monkeypatch.setattr(BK, "_policy_rates", lambda: ({"XXX": POLICY}, FED))
    monkeypatch.setattr(BK, "ROOT", tmp_path)
    monkeypatch.setattr(CAP, "ROOT", tmp_path)
    monkeypatch.setattr(CAP, "_git", lambda *a: None)
    monkeypatch.setattr(CAP, "load_reference", lambda *a, **k: {})
    monkeypatch.setattr(CAP, "monthly_impact", lambda *a, **k: {})
    monkeypatch.setattr(CAP, "algo_capital", lambda *a, **k: 100000)
    return tmp_path


def _write_positions(root, rel: str, eff: str, run_date: str | None, as_of: str = "2026-10"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    cols = POS_COLUMNS if run_date is not None else POS_COLUMNS[:-2]
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        row = [as_of, eff, "fx", INST, "long", "50.000"]
        if run_date is not None:
            row += [f"{eff}-03", run_date]
        w.writerow(row)


def _write_log(root, rel: str, eff: str, run_date: str, as_of: str = "2026-11"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("as_of,effective_from,scheduled_date,run_date,days_late,status,n_positions\n"
                 f"{as_of},{eff},{eff}-03,{run_date},0,on time,1\n", encoding="utf-8")


def _alg(eff: str = "2026-11", live_months=(), v11_eff: str = "2026-11") -> dict:
    pos10 = [{**POS[0], "effective_from": eff}]
    pos11 = [{**POS[0], "effective_from": v11_eff}]
    return {"months": list(live_months), "positions": pos10, "rebalance": {"live_start_month": "2026-11"},
            "capacity": {}, "v11": {"months": [], "positions": pos11, "live_start_month": "2026-12", "capacity": {}}}


def _v10(root, run_date: str | None, today: date, eff: str = "2026-11", live_months=()):
    _write_positions(root, "results/systematic/positions.csv", eff, run_date)
    return BK.algo_book(_alg(eff, live_months), _mb(), today)["versions"][0]


# ----------------------------------------------------------------------------- 1. the 4 Nov 2026 case
def test_q001_estimate_base_is_the_rebalance_date(_hermetic):
    v10 = _v10(_hermetic, "2026-11-04", date(2026, 11, 9))
    est = v10["estimate"]
    assert est["base_date"] == "2026-11-04", f"estimate based on {est['base_date']}, before the 4 Nov rebalance"
    p = est["positions"][0]
    assert p["base_date"] == "2026-11-04" and p["base_mark"] == _val("2026-11-04"), p
    assert est["series"][0][0] == "2026-11-05", est["series"][:3]            # first close after the rebalance
    assert [d for d, _ in est["series"]] == ["2026-11-05", "2026-11-06", "2026-11-09"]
    assert est["series"][-1][1] == _expected("2026-11-04", date(2026, 11, 4), date(2026, 11, 9))
    assert v10["mtd_pct"] == est["mtd_pct"] == est["series"][-1][1]
    assert est["rebalance_date"] == "2026-11-04"
    assert est["base_source"].startswith("run_date of results/systematic/positions.csv"), est["base_source"]
    # the books' index: no estimate point on or before the rebalance date
    pts = [x for x in v10["series"] if x[2] == "estimate"]
    assert pts and min(x[0] for x in pts) == "2026-11-05", pts
    assert min(h[0] for h in p["mark_history"]) >= "2026-10-25"           # history from 10 days before the base


def test_q001_label_and_note_say_from_the_rebalance_date(_hermetic):
    est = _v10(_hermetic, "2026-11-04", date(2026, 11, 9))["estimate"]
    assert est["label"] == "estimate from the actual rebalance date"
    note = est["note"]
    for s in ("from the actual rebalance date", "2026-11-04", "frozen full-month convention",
              "official", "replaces", "re-run"):
        assert s in note, (s, note)


# ----------------------------------------------------------------------------- 2. clamp
def test_q001_run_before_the_month_is_clamped_to_the_previous_month_end(_hermetic):
    eff, run = "2026-12", "2026-11-26"
    v10 = _v10(_hermetic, run, date(2026, 12, 3), eff=eff)
    est = v10["estimate"]
    assert est["base_date"] == "2026-11-30", est["base_date"]               # never last month's moves
    assert est["positions"][0]["base_date"] == "2026-11-30"
    assert est["series"][0][0] == "2026-12-01"
    assert est["series"][-1][1] == _expected("2026-11-30", date(2026, 11, 30), date(2026, 12, 3))
    assert est["rebalance_date"] == run
    assert all(x[0] > "2026-11-30" for x in v10["series"] if x[2] == "estimate")


# ----------------------------------------------------------------------------- 3. weekend run date
def test_q001_weekend_run_date_uses_the_last_mark_on_or_before_it(_hermetic):
    eff, run = "2027-01", "2027-01-03"                                       # a Sunday
    est = _v10(_hermetic, run, date(2027, 1, 6), eff=eff)["estimate"]
    assert est["base_date"] == run
    p = est["positions"][0]
    assert p["base_date"] == "2026-12-31", p                                 # 1 Jan: no close; last mark on or before
    assert est["series"][0][0] == "2027-01-04"                               # first close after the run date
    first = est["series"][0][1]
    assert first == _expected("2026-12-31", date(2027, 1, 3), date(2027, 1, 4))    # carry from the run date: 1 day
    assert est["series"][-1][1] == _expected("2026-12-31", date(2027, 1, 3), date(2027, 1, 6))


# ----------------------------------------------------------------------------- 4. a re-run restamps run_date
def test_q001_rerun_with_identical_positions_moves_the_base_and_says_so(_hermetic):
    first = _v10(_hermetic, "2026-11-04", date(2026, 11, 13))["estimate"]
    rerun = _v10(_hermetic, "2026-11-10", date(2026, 11, 13))["estimate"]   # same positions, restamped
    assert first["base_date"] == "2026-11-04" and rerun["base_date"] == "2026-11-10"
    assert rerun["series"][0][0] == "2026-11-11"
    assert rerun["series"][-1][1] == _expected("2026-11-10", date(2026, 11, 10), date(2026, 11, 13))
    assert "2026-11-10" in rerun["note"] and "re-run" in rerun["note"] and "moves the base" in rerun["note"]


# ----------------------------------------------------------------------------- 5. which date each version uses
def test_q001_base_date_source_of_each_version(_hermetic):
    root = _hermetic
    # v1.0: the positions file's run_date, for the positions' effective month only
    _write_positions(root, "results/systematic/positions.csv", "2026-11", "2026-11-04")
    assert BK.rebalance_date("v1.0", "2026-11") == ("2026-11-04", "run_date of results/systematic/positions.csv")
    assert BK.rebalance_date("v1.0", "2026-12")[0] is None
    # v1.1 today: no run_date column and no rebalance log -> none: full-month base, labelled as such
    _write_positions(root, "results/systematic_v1.1/positions.csv", "2026-11", None)
    when, src = BK.rebalance_date("v1.1", "2026-11")
    assert when is None and "full month" in src, src
    v11 = BK.algo_book(_alg(), _mb(), date(2026, 11, 9))["versions"][1]
    est = v11["estimate"]
    assert est["base_date"] == "2026-10-31" and est["series"][0][0] == "2026-11-02"
    assert est["rebalance_date"] is None and est["label"] == "estimate, month to date (full month: no rebalance date)"
    assert "no rebalance date" in est["note"] and "2026-10-31" in est["note"]
    # v1.1 from its own stamped step: its rebalance log row for the effective month, then the positions' run_date
    _write_log(root, "results/systematic_v1.1/rebalance_log.csv", "2026-12", "2026-12-03")
    _write_positions(root, "results/systematic_v1.1/positions.csv", "2026-12", None, as_of="2026-11")
    assert BK.rebalance_date("v1.1", "2026-12") == ("2026-12-03", "run_date of results/systematic_v1.1/rebalance_log.csv")
    _write_positions(root, "results/systematic_v1.1/positions.csv", "2026-12", "2026-12-04", as_of="2026-11")
    assert BK.rebalance_date("v1.1", "2026-12") == ("2026-12-04", "run_date of results/systematic_v1.1/positions.csv")
    # direct callers without a run date keep the full-month convention (unchanged behaviour)
    old = BK.algo_estimate(POS, _mb(), "2026-11", date(2026, 11, 9))
    assert old["base_date"] == "2026-10-31" and old["series"][0][0] == "2026-11-02"


# ----------------------------------------------------------------------------- 6. official figures unchanged
def test_q001_official_month_end_figures_are_unchanged(_hermetic):
    nov = {"month": "2026-11", "live": True, "net": 0.0125, "fx_gross": 0.013, "bond_gross": 0.0, "cost": 0.0005}
    late = _v10(_hermetic, "2026-12-04", date(2026, 12, 9), eff="2026-12", live_months=[nov])
    off = [x for x in late["series"] if x[2] == "official"]
    assert off == [["2026-10-31", 100.0, "official"], ["2026-11-30", 101.25, "official"]]
    assert late["official_index"] == 101.25
    assert late["attribution"]["official_books"][0] == {"key": "FX", "pnl_pct": 1.3}
    est_pts = [x for x in late["series"] if x[2] == "estimate"]
    assert est_pts[0][0] == "2026-12-07" and late["estimate"]["base_date"] == "2026-12-04"
