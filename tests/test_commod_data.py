"""Build 0 tests for the commodity data layer (docs/prereg/T20-T22_commodity_trials.md §6: A6, A9 and A11 stay in
the suite).

Synthetic tests always run.  The data-backed tests read the private Norgate snapshot (EM_MACRO_DATA pointing at a
clone of EthanC100/em-macro-data) and are skipped when it is absent, e.g. in CI.  They encode the assertions
exactly as pre-registered; see results/T20-T22/build0.md for which of them hold on the 2026-11 snapshot.
"""
import os

import numpy as np
import pandas as pd
import pytest

from em_macro import commod_build0 as B
from em_macro import commod_data as CD


# ------------------------------------------------------------------------------------------- synthetic fixture
def _write_contract(folder, name, start, end, price=50.0, skip=()):
    days = [d for d in pd.bdate_range(start, end) if d.strftime("%Y-%m-%d") not in skip]
    df = pd.DataFrame({"date": [d.strftime("%Y-%m-%d") for d in days], "open": price, "high": price,
                       "low": price, "close": price + np.arange(len(days)) * 0.01, "volume": 1,
                       "open_interest": 1})
    df.to_csv(folder / f"{name}.csv", index=False)


@pytest.fixture()
def toy_cl(tmp_path, monkeypatch):
    folder = tmp_path / "norgate" / CD.SNAPSHOT / "contracts" / "CL"
    folder.mkdir(parents=True)
    # CLK20's last trade date was 21 April 2020; later contracts run past the snapshot's end
    _write_contract(folder, "CL-2020K", "2019-01-02", "2020-04-21")
    _write_contract(folder, "CL-2020M", "2019-01-02", "2020-05-19")
    _write_contract(folder, "CL-2020N", "2019-01-02", "2020-06-22")
    _write_contract(folder, "CL-2020Q", "2019-01-02", "2020-07-21")
    for code in "UVXZ":
        _write_contract(folder, f"CL-2020{code}", "2019-01-02", "2020-08-14")
    for code in CD.MONTH_CODES:
        _write_contract(folder, f"CL-2021{code}", "2019-01-02", "2020-08-14")
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path))
    return CD.MarketData("CL")


def test_april_2020_selects_clm20(toy_cl):
    """Pre-registered unit test (§2.3): on the April 2020 decision date the rule selects CLM20, not CLK20."""
    r = toy_cl.rolls.loc[pd.Period("2020-04", "M")]
    assert r["execution"] == pd.Timestamp("2020-04-03")
    assert r["decision"] == pd.Timestamp("2020-04-02")
    assert r["F1"] == "CL-2020M"
    assert r["F2"] == "CL-2020N"
    assert r["F13"] == "CL-2021M"


def test_notice_buffer_and_first_settlement(toy_cl):
    ct, r = toy_cl.contracts, toy_cl.rolls.dropna(subset=["F1"])
    for _, row in r.iterrows():
        assert ct.at[row["F1"], "notice"] > row["execution"] + pd.Timedelta(days=CD.BUFFER_DAYS)
        assert ct.at[row["F1"], "first"] <= row["decision"]


def test_live_contract_uses_exchange_rule(toy_cl):
    ct = toy_cl.contracts
    # live contracts (last bar = snapshot's latest date) take the exchange LTD rule
    assert ct.at["CL-2021F", "live"]
    assert ct.at["CL-2021F", "ltd"] == ct.at["CL-2021F", "ltd_rule"]
    # expired ones take Norgate's final settlement
    assert ct.at["CL-2020K", "ltd"] == pd.Timestamp("2020-04-21")


def test_chained_index_same_contract(toy_cl):
    d = toy_cl.daily_returns("F1")
    for day, row in d.iterrows():
        held = toy_cl.held_series("F1").shift(1).get(day)
        assert row["contract"] == held


def test_cl_ltd_rule_holiday():
    cal = CD.BizCal(pd.bdate_range("2026-01-02", "2026-11-04"))
    # 25 Dec 2026 is a holiday (Friday): LTD = 3 business days before 24 Dec = 21 Dec 2026
    assert CD.LTD_RULES["CL"](cal, 2027, 1) == pd.Timestamp("2026-12-21")
    assert CD.LTD_RULES["HE"](cal, 2026, 12) == pd.Timestamp("2026-12-14")
    assert CD.FND_RULES["LBD_PREV"](cal, 2026, 12) == pd.Timestamp("2026-11-30")


def test_good_friday():
    assert CD._good_friday(2020) == pd.Timestamp("2020-04-10").date()
    assert CD._good_friday(2026) == pd.Timestamp("2026-04-03").date()


def test_consecutive_runs_and_gap_limit():
    flags = pd.Series([False, True, True, False] + [True] * 6 + [False],
                      index=pd.bdate_range("2020-01-01", periods=11))
    runs = B._consecutive_runs(flags)
    assert [n for _, _, n in runs] == [2, 6]
    assert sum(n > B.GAP_LIMIT for _, _, n in runs) == 1


def test_rank_weights():
    w = B.rank_weights(pd.Series({"a": 0.3, "b": -0.1, "c": 0.0, "d": np.nan}))
    assert abs(w.abs().sum() - 2) < 1e-12 and abs(w.sum()) < 1e-12
    assert w["a"] > 0 > w["b"]


def test_no_lme_market():
    assert not any("LME" in m.exchange for m in CD.MARKETS.values())


def test_universe_sizes():
    assert len(CD.COMMODITIES) == 24 and len(CD.FINANCIALS) == 10 and len(CD.XS_UNIVERSE) == 20
    assert not {"GC", "SI", "PL", "PA"} & set(CD.XS_UNIVERSE)


# ------------------------------------------------------------------------------------------- data-backed (A6, A9, A11)
HAVE_DATA = (CD.snapshot_dir() / "contracts" / "CL").is_dir()
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="private Norgate snapshot not available (EM_MACRO_DATA)")


@pytest.fixture(scope="module")
def markets():
    return {c: CD.MarketData(c) for c in CD.available_markets() if CD.MARKETS[c].kind == "commodity"}


@needs_data
def test_a6_april_2020_real(markets):
    assert markets["CL"].rolls.at[pd.Period("2020-04", "M"), "F1"] == "CL-2020M"


@needs_data
@pytest.mark.parametrize("code", CD.COMMODITIES)
def test_a6_first_settlement_and_notice(markets, code):
    res = B.a6_roll_checks(markets[code])
    assert res["first_settle_after_decision"] == 0, res["first_settle_examples"]
    assert res["notice_violations"] == 0


@needs_data
@pytest.mark.parametrize("code", CD.COMMODITIES)
def test_a6_never_in_last_10_trading_days(markets, code):
    res = B.a6_roll_checks(markets[code])
    assert res["F1_last10_violations"] == 0, res["F1_last10_examples"]
    assert res["F2_last10_violations"] == 0, res["F2_last10_examples"]


@needs_data
@pytest.mark.parametrize("code", CD.COMMODITIES)
def test_a9_no_unresolved_quality_issue(markets, code):
    md = markets[code]
    rets = {w: md.daily_returns(w) for w in ("F1", "F2")}
    _, issues = B.a9_quality(md, rets)
    issues = B.resolve_spikes(md, issues)
    if not issues.empty:
        assert not (issues["status"] == "unresolved").any(), issues[issues["status"] == "unresolved"]


@needs_data
@pytest.mark.parametrize("code", CD.COMMODITIES)
def test_a11_f2_f13_listed(markets, code):
    res = B.a11_listed(markets[code])
    assert res["violations"] == 0, res["examples"]


def test_draft_last_days_guard_is_off_by_default(toy_cl):
    """The pre-registered rule is the default; the draft Amendment 3 guard only applies when asked for and keeps
    the April 2020 choice (CLM20 has 12 trading days left at the May 2020 execution)."""
    base = toy_cl.roll()
    assert base.equals(toy_cl.rolls)
    g = toy_cl.roll(last_days_guard=10)
    assert g.at[pd.Period("2020-04", "M"), "F1"] == "CL-2020M"
    ct = toy_cl.contracts
    for m, row in g.dropna(subset=["F1"]).iterrows():
        nxt = toy_cl.next_execution(m)
        if nxt <= toy_cl.latest:
            assert toy_cl.calendar.count_between(nxt, ct.at[row["F1"], "ltd"]) > 10
