"""No mark is dated after its run's day (2026-11-17, docs/config_changes.md).

On 11 Nov 2026 the Ledger site showed "latest mark 30 Nov 2026": CLP's row ``2026-11-30,...,panel_monthly
fx_per_usd_end:CHL`` (the panel's unfinished November, dated at its month end) was still in data/ledger/marks.csv,
and the site's latest mark was the maximum date over every row. Q006 (14 Nov) had kept new *fallbacks* out of the
future and kept that row from pricing anything, but a *primary* could still be future-dated: datos.gov.co publishes
Colombia's TRM for tomorrow today, so ledger-daily's 22:12 UTC run wrote ``2026-11-14,COP`` on 13 Nov, a daily
first-hand mark that could act on a stop. The rule now:
1. every source, primary or fallback, keeps only observations dated on or before the run's day (history too);
2. the marks file never holds a row dated after the day it was fetched: ``write_marks`` refuses such a row and drops
   any already there, ``read_marks`` leaves them out, and so latest marks, the Janus series and the books skip them;
3. the site's latest mark is never after the build's day (tests/test_site_build.py checks the built site).
Made-up sources and marks in a temporary directory; never data/ledger.
"""
import json
from datetime import date

from ledger import books as BK
from ledger import janus as JN
from ledger import marks as M

TODAY = date(2026, 11, 13)
COP_ROW = {"instrument": "COP", "country": "Colombia", "iso3": "COL", "book": "fx", "kind": "fx", "unit": "COP per USD",
           "frequency": "daily", "source": "datos_gov_co", "source_id": "32sa-8pi3", "source_url": "",
           "fallback_source": "", "fallback_id": "", "aliases": "USD/COP|USDCOP"}


def trm(*days):
    """datos.gov.co's answer: TRM rows newest first, the first one effective tomorrow."""
    rows = [{"vigenciadesde": f"{d.isoformat()}T00:00:00.000", "valor": str(4000 + d.day)} for d in sorted(days, reverse=True)]
    return lambda url, **kw: json.dumps(rows).encode()


def row(d, value, fetched, inst="COP", freq="daily", note=""):
    return {"date": d, "instrument": inst, "value": value, "unit": "COP per USD", "frequency": freq,
            "source": "datos_gov_co 32sa-8pi3", "source_url": "", "fetched_at": fetched, "note": note}


def test_primary_never_dated_after_today():
    """13 Nov 22:12 UTC: the source already has the 14 Nov TRM; the mark is the 13 Nov one, history stops at 12 Nov."""
    get = trm(date(2026, 11, 14), date(2026, 11, 13), date(2026, 11, 12), date(2026, 11, 11))
    out = M.fetch_instrument(COP_ROW, {}, {}, TODAY, get, previous={})
    assert (out["date"], out["value"], out["note"]) == ("2026-11-13", "4013", ""), out
    assert out["_history"] and all(d < TODAY for d, _ in out["_history"]), out["_history"]
    assert M.mark_can_act(out)


def test_primary_with_only_future_points_falls_through():
    """A source with nothing on or before today is a failed source: the previous mark is kept (no fallback here)."""
    prev = row("2026-11-12", "4012", "2026-11-12T22:12:00+00:00")
    out = M.fetch_instrument(COP_ROW, {}, {}, TODAY, trm(date(2026, 11, 14)), previous={"COP": prev})
    assert out["date"] == "2026-11-12" and out["note"].startswith("kept previous mark"), out
    assert "after today" in out["note"], out["note"]


def test_marks_file_never_keeps_a_future_row(tmp_path, capsys):
    path = tmp_path / "marks.csv"
    good = row("2026-11-13", "4013", "2026-11-13T22:12:00+00:00")
    bad_existing = row("2026-11-30", "980.59", "2026-11-13T13:29:28+00:00", inst="CLP", freq="monthly",
                       note="fallback panel_monthly fx_per_usd_end:CHL after: mindicador dolar: timed out")
    # a file written before the rule, with the CLP 30 Nov row in it
    path.write_text(",".join(M.MARK_COLUMNS) + "\n" + "\n".join(
        ",".join(r[c] for c in M.MARK_COLUMNS) for r in (good, bad_existing)) + "\n", encoding="utf-8")
    assert [r["date"] for r in M.read_marks(path)] == ["2026-11-13"]
    assert len(M.read_marks(path, include_future=True)) == 2

    # the next run: a future row is not written, and the old one is dropped from the file (named on stderr)
    n = M.write_marks([row("2026-11-14", "4014", "2026-11-13T22:12:00+00:00")], path)
    assert n == 1
    raw = M.read_marks(path, include_future=True)
    assert [(r["instrument"], r["date"]) for r in raw] == [("COP", "2026-11-13")], raw
    assert not any(M.future_dated(r) for r in raw)
    err = capsys.readouterr().err
    assert "dropped CLP 2026-11-30" in err and "not written COP 2026-11-14" in err

    # on the day itself the real mark for that date is written as usual
    M.write_marks([row("2026-11-14", "4014", "2026-11-14T22:12:00+00:00")], path)
    assert M.latest_marks(path)["COP"]["date"] == "2026-11-14"


def test_readers_skip_future_rows():
    """Rows passed in directly (not through read_marks) are filtered too: latest marks, the Janus series, the books."""
    rows = [row("2026-11-12", "4012", "2026-11-12T22:12:00+00:00"), row("2026-11-14", "4014", "2026-11-13T22:12:00+00:00")]
    assert M.future_dated(rows[1]) and not M.future_dated(rows[0])
    assert M.latest_marks(rows=rows)["COP"]["date"] == "2026-11-12"
    assert [x[0] for x in JN.series(rows, "COP")] == [date(2026, 11, 12)]
    assert [x[0] for x in BK.MarkBook(rows=rows).series("COP", all_marks=True)] == [date(2026, 11, 12)]
    assert M.marks_on_or_before("COP", date(2026, 12, 1), rows)["date"] == "2026-11-12"
