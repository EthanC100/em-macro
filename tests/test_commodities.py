"""The Commodities book (ledger/commodities.py, C12): K x the T26 shadow, read-only on the shadow, no price published.
Synthetic data only: the shadow's output comes from em_macro.t2526 on the synthetic store of test_t2526."""
import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ledger import commodities as COM
from test_t2526 import _daily, live, store   # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2027, 2, 26)


@pytest.fixture()
def book(live):
    _daily(live, TODAY)                                  # the shadow goes live and writes its files (T25 and T26)
    assert json.loads((live["out"] / "GO_LIVE.json").read_text())["confirmed"]
    return live


def _hashes(folder: Path) -> dict:
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def test_k_is_frozen_from_the_t22_design_period_backtest():
    m = pd.read_csv(ROOT / "results/T20-T22/monthly_net.csv", index_col=0)
    r = m["T22 sleeve|full|decisive"].loc["2000-01":"2019-12"]
    vol = r.std(ddof=1) * math.sqrt(12)
    assert len(r) == 240 and r.notna().all()
    assert round(100 * vol, 4) == COM.K_DERIVATION["ann_vol_pct"] == 9.0675
    assert COM.K == round(0.10 / vol, 4) == 1.1028
    assert hashlib.sha256((ROOT / "results/T20-T22/monthly_net.csv").read_bytes()).hexdigest() == \
        COM.K_DERIVATION["source_sha256"]


def test_book_returns_equal_k_times_the_shadow_exactly(book):
    b = COM.build(TODAY, book["root"], total_return=False)
    shadow = pd.read_csv(book["out"] / "T26" / "monthly.csv")
    assert b["live"] and len(b["monthly"]) == len(shadow) == 3
    for row, (_, s) in zip(b["monthly"], shadow.iterrows()):
        assert row["month"] == s["month"]
        assert row["shadow_net_pct"] == float(s["net_decisive_%"])
        assert row["book_net_pct"] == COM.K * float(s["net_decisive_%"])        # exactly k x the shadow
    # the equity curve compounds exactly those monthly returns at each month's last point
    ser = dict((d, v) for d, v in b["series"])
    idx = pd.read_csv(book["out"] / "T26" / "index.csv")
    lasts = idx.groupby(idx["date"].str[:7])["date"].max()
    cum = 100.0
    for row in b["monthly"]:
        cum *= 1 + row["book_net_pct"] / 100
        assert ser[lasts[row["month"]]] == pytest.approx(cum, abs=1e-5)
    assert b["series"][0][1] == 100.0 and b["series"][0][0] < idx["date"].iloc[0]
    # within a month the book moves k x the shadow's month-to-date return
    first_day = idx.iloc[0]
    assert ser[first_day["date"]] == pytest.approx(100 * (1 + COM.K * (first_day["index_net_decisive"] / 100 - 1)), abs=1e-5)
    assert b["max_drawdown_pct"] <= 0 and b["vol"]["target_pct"] == 10.0


def test_positions_have_contracts_and_risk_shares_but_no_price(book, monkeypatch):
    res = COM.update(book["root"], book["base"], log=lambda *_: None)
    assert res["written"] and res["month"] == "2027-02"
    pub = book["root"] / "data/commodities/positions.csv"
    rows = pd.read_csv(pub, dtype=str).fillna("")
    assert list(rows.columns) == COM.POSITION_COLUMNS
    shadow = pd.read_csv(book["out"] / "T26" / "positions.csv")
    held = shadow[(shadow["month"] == "2027-02") & (shadow["held_weight"] != 0)]
    assert len(rows) == len(held) > 0
    assert all(re.fullmatch(r"\d+", n) for n in rows["contracts"])
    assert sum(float(x) for x in rows["risk_share_pct"]) == pytest.approx(100, abs=0.05)
    assert set(rows["direction"]) <= {"long", "short"}
    # contracts = k x weight x US$100m / (the execution settlement x multiplier), from the private files
    from em_macro import commod_data as CD
    from em_macro import t2526 as M
    r0 = rows.iloc[0]
    mk = M.load_markets([r0["market"]], pd.Period("2027-02", "M"), book["base"])[r0["market"]]
    F = mk.md.settle(r0["contract"], mk.rolls.at[pd.Period("2027-02", "M"), "execution"])
    w = float(held[held["market"] == r0["market"]]["held_weight"].iloc[0])
    assert int(r0["contracts"]) == abs(round(COM.K * w * COM.CAPITAL_USD / (F * mk.m.tick_value / mk.m.tick)))
    # no settlement value anywhere in the public outputs. The book reads the private contract files (Norgate units),
    # so every decimal number it publishes must lie below the lowest synthetic price, and none may equal a price.
    # (Percentages can coincide with prices in Databento's raw units for HG and SI, which the book never reads.)
    prices = set()
    for c, ser in book["series"].items():
        for s in ser.values():
            prices |= {round(x, 2) for x in s.values}
    lowest = min(prices)
    app = json.dumps(COM.build(TODAY, book["root"], total_return=False))
    for text in (pub.read_text(), app):
        nums = {round(float(x), 2) for x in re.findall(r"-?\d+\.\d+", text)}
        assert max(abs(n) for n in nums) < lowest, (sorted(nums)[-3:], lowest)
        assert not nums & prices
    b = COM.build(TODAY, book["root"], total_return=False)
    assert b["positions"] and all(set(p) <= set(COM.POSITION_COLUMNS) for p in b["positions"])


def test_no_write_path_to_the_shadow_or_the_private_store(book, monkeypatch):
    shadow, base = book["out"], book["base"]
    before_s, before_p = _hashes(shadow), _hashes(base)
    writes = []
    real_open, real_write = Path.open, Path.write_text

    def guard(path):
        p = Path(path).resolve()
        if shadow.resolve() in p.parents or base.resolve() in p.parents:
            writes.append(str(p))
            raise AssertionError(f"write to a read-only file: {p}")

    def g_open(self, mode="r", *a, **k):
        if any(x in mode for x in "wax+"):
            guard(self)
        return real_open(self, mode, *a, **k)

    def g_write(self, *a, **k):
        guard(self)
        return real_write(self, *a, **k)
    monkeypatch.setattr(Path, "open", g_open)
    monkeypatch.setattr(Path, "write_text", g_write)
    import builtins
    real_bopen = builtins.open

    def b_open(file, mode="r", *a, **k):
        if isinstance(file, (str, Path)) and any(x in mode for x in "wax+"):
            guard(file)
        return real_bopen(file, mode, *a, **k)
    monkeypatch.setattr(builtins, "open", b_open)
    COM.update(book["root"], base, log=lambda *_: None)
    COM.build(TODAY, book["root"], total_return=False)
    monkeypatch.undo()
    assert not writes and _hashes(shadow) == before_s and _hashes(base) == before_p
    # statically: the module's only write is the book's own positions file, under data/commodities
    src = (ROOT / "ledger/commodities.py").read_text()
    assert len(re.findall(r'open\("w"|\.write_text\(|\.write_bytes\(|mkdir\(', src)) == 2      # open("w") + mkdir
    assert 'out.open("w"' in src and "out.parent.mkdir" in src
    assert COM.paths(book["root"])["book_positions"].parent == book["root"] / "data" / "commodities"


def test_before_go_live_the_book_shows_its_start(live):
    b = COM.build(date(2026, 11, 20), live["root"], total_return=False)
    assert not b["live"] and b["status"] == "Starts 3 Dec 2026" and b["series"] == [] and b["positions"] == []
    assert b["start"] == "2026-12-03" and not b["in_fund"]
    assert COM.update(live["root"], live["base"], log=lambda *_: None) == {"written": False}
    assert not (live["root"] / "data/commodities").exists()


def test_outside_the_fund_and_wired_into_the_app():
    from ledger import fund as F
    assert set(F.SHARES) == {"algorithm v1.1", "janus"}
    html = (ROOT / "ledger/site/index.html").read_text()
    assert html.index('src="commodities.js"') < html.index('src="app.js"') and 'href="#/commodities"' in html
    assert "pages.commodities" in (ROOT / "ledger/site/commodities.js").read_text()
    b = COM.build_safe(date(2026, 11, 11))
    assert b["name"] == "Commodities" and b["k"] == COM.K


def test_ledger_daily_commodities_step_can_never_stop_the_marks():
    import yaml
    wf = yaml.safe_load((ROOT / ".github/workflows/ledger-daily.yml").read_text())
    job = wf["jobs"]["daily"]
    steps = job["steps"]
    names = [s.get("name") for s in steps]
    com = next(s for s in steps if s.get("id") == "commodities")
    commit = next(s for s in steps if s.get("id") == "commit")
    assert com["continue-on-error"] is True and 0 < com["timeout-minutes"] < job["timeout-minutes"]
    assert names.index(com["name"]) < names.index(commit["name"]) and "if" not in commit   # commit runs regardless
    assert job["defaults"]["run"]["shell"] == "bash"                     # -eo pipefail: a failure fails the step
    assert "data/commodities" in commit["run"]
    alert = next(s for s in steps if s.get("name") == "Commodities book alert")
    assert "steps.commodities.outcome == 'failure'" in alert["if"] and alert["if"].startswith("always()")
    assert '"[ALERT] Commodities book step failed"' in alert["run"]
    close = next(s for s in steps if s.get("name") == "Close alert issues after a successful run")
    assert 'startswith("[ALERT] ledger-daily")' in close["run"]          # a green run does not close the book's alert
