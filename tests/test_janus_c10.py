"""Config change C10 (approved by Ethan 2026-11-11, before C08's first review): GBP is marked on the ECB cross, US
dollars per pound = the ECB's US dollars per euro / pounds per euro, replacing the Bank of England's XUDLUSS (a
business day late, and refused to cloud clients). Every test here fails before C10 and passes after."""
from datetime import date
from pathlib import Path

import pytest

from ledger import janus as J
from ledger import marks as M

ROOT = Path(__file__).resolve().parents[1]
HEAD = "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"
USD = HEAD + "".join(f"EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,{d},{v}\n" for d, v in
                     (("2026-11-06", 1.1630), ("2026-11-09", 1.1655), ("2026-11-10", 1.1662)))
GBP = HEAD + "".join(f"EXR.D.GBP.EUR.SP00.A,D,GBP,EUR,SP00,A,{d},{v}\n" for d, v in
                     (("2026-11-06", 0.86890), ("2026-11-09", 0.86875), ("2026-11-10", 0.86883)))


def fake(url, **kw):
    for ccy, body in (("D.USD.EUR", USD), ("D.GBP.EUR", GBP)):
        if ccy in url:
            return body.encode()
    raise RuntimeError(f"{url}: down")


def test_the_ecb_cross_gives_us_dollars_per_pound():
    d, v, url = M.fetch_ecb_exr("GBP/USD", fake)
    assert (d, v) == (date(2026, 11, 10), round(1.1662 / 0.86883, 6)) and "D.GBP.EUR" in url
    assert M.fetch_ecb_exr("GBP", fake)[1] == round(0.86883 / 1.1662, 6)          # CCY alone: pounds per dollar
    pts, _ = M.ecb_exr_history("GBP/USD", date(2026, 11, 9), fake)
    assert [p[0] for p in pts] == [date(2026, 11, 6), date(2026, 11, 9), date(2026, 11, 10)]
    with pytest.raises(ValueError, match="only CCY or CCY/USD"):
        M.fetch_ecb_exr("GBP/EUR", fake)


def test_gbp_is_marked_on_the_ecb_cross_and_can_act():
    row = {r["instrument"]: r for r in M.load_registry()}["GBP"]
    assert (row["source"], row["source_id"], row["unit"]) == ("ecb_exr", "GBP/USD", "USD per GBP")
    m = M.fetch_instrument(row, {}, {}, date(2026, 11, 11), fake)
    assert (m["date"], m["source"], m["frequency"]) == ("2026-11-10", "ecb_exr GBP/USD", "daily") and M.mark_can_act(m)
    assert float(m["value"]) == pytest.approx(1.1662 / 0.86883, abs=1e-5)
    assert len(m["_history"]) == 2                                    # 6 and 9 Nov stored too: one consistent series


def test_the_watchlist_resolves_gbp_on_the_ecb_cross():
    gbp = {w["instrument"]: w for w in J.load_watchlist()}["GBP"]
    assert "D.GBP.EUR.SP00.A" in gbp["resolution_source"] and "XUDLUSS" not in gbp["resolution_source"]
    doc = (ROOT / "docs/config_changes.md").read_text(encoding="utf-8")
    assert "| C10 | 2026-11-11 |" in doc and "## C10" in doc and "Approved by Ethan on 2026-11-11" in doc
