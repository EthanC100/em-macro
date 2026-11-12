"""Milestone E, criterion E-08: the public currency data, point in time, and the reproduction of carry and
time-series momentum with the engine (manhattan/factors/). Public data only; nothing after 2019-12-31 is read.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest

from manhattan import ledger as L
from manhattan import roles
from manhattan.engine import backtest
from manhattan.factors import public_fx as fx
from manhattan.factors import reproduce

ROOT = Path(__file__).resolve().parents[1]


def test_the_panel_is_read_to_the_cut_off_and_no_further(tmp_path):
    p = tmp_path / "panel.csv"
    p.write_text("date,FX_BR,POL_BR,US_FF,OTHER\n2019-12-30,4.0,4.5,1.5,7\n2019-12-31,4.1,,1.6,8\n"
                 "2020-01-02,not a number,never parsed,x,y\nthis line is not even a row\n", encoding="utf-8")
    days, data = fx.read_panel(p, date(2019, 12, 31), {"FX_BR", "POL_BR", "US_FF"})
    assert [str(d) for d in days] == ["2019-12-30", "2019-12-31"] and set(data) == {"FX_BR", "POL_BR", "US_FF"}
    assert data["FX_BR"].tolist() == [4.0, 4.1] and np.isnan(data["POL_BR"][1])
    with pytest.raises(ValueError):                                   # asked to go on, it meets the row it must not read
        fx.read_panel(p, date(2020, 1, 31))
    days, _ = fx.read_panel(end=date(2005, 1, 31))                    # the real file
    assert str(days[0]) == "2005-01-03" and str(days[-1]) == "2005-01-31"
    assert fx.CUTOFF == date(2019, 12, 31) and fx.read_panel()[0][-1] == np.datetime64("2019-12-31")


def test_the_deposit_index_by_hand():
    d = np.array(["2010-01-07", "2010-01-08", "2010-01-11", "2010-01-12"], dtype="datetime64[D]")
    spot = np.array([2.0, 2.02, np.nan, 1.98])                         # no fixing on the Monday
    rate = np.array([7.3, np.nan, 10.95, 10.95])                       # per cent a year; one day without a rate
    days, v = fx.deposit_index(d, spot, rate)
    assert [str(x) for x in days] == ["2010-01-07", "2010-01-08", "2010-01-12"]
    one = 2.0 / 2.02 * (1 + 0.073 * 1 / 365)
    two = one * 2.02 / 1.98 * (1 + 0.073 * 4 / 365)                    # Friday to Tuesday at Friday's rate in force (7.3%)
    assert v == pytest.approx([1.0, one, two])


def test_the_store_stamps_everything_a_day_late_and_only_the_exploration_window_opens():
    store = fx.store()
    assert store.names() == sorted(["us_ff"] + [f"{k}_{c}" for k in ("fx", "pol", "dep") for c in fx.CURRENCIES])
    w = reproduce.window(store)
    assert w.role == roles.EXPLORATION and w.end == date(2019, 12, 31)
    d, _ = w.as_of("fx_BR", date(2010, 6, 15))
    assert str(d[-1]) == "2010-06-14"                                  # the day's own fixing is not out yet
    assert str(w.final("dep_BR")[0][-1]) == "2019-12-30"               # the last fixing is published in 2020
    with pytest.raises(roles.RoleError):
        reproduce.window(store, date(2020, 1, 2))
    ins = fx.instruments(("BR", "MX"), cost=0.0002)
    assert [(i.name, i.price, i.kind, i.rate, i.cost) for i in ins] == [("BR", "dep_BR", "cash", "us_ff", 0.0002),
                                                                        ("MX", "dep_MX", "cash", "us_ff", 0.0002)]
    m, x = fx.monthly(np.array(["2010-01-29", "2010-02-01", "2010-02-02"], dtype="datetime64[D]"), np.array([0.01, 0.02, -0.01]))
    assert [str(k) for k in m] == ["2010-01", "2010-02"] and x == pytest.approx([0.01, 1.02 * 0.99 - 1])


def test_the_engines_volatility_is_pandas_and_its_trend_weights_are_t01s():
    import pandas as pd
    rng = np.random.default_rng(4)
    r = 0.03 * rng.standard_normal(40)
    want = pd.Series(r).ewm(com=reproduce.EWMA_COM_MONTHS, min_periods=12).std().iloc[-1] * np.sqrt(12)
    assert reproduce.ewma_vol(r) == pytest.approx(want, rel=1e-12)
    assert np.isnan(reproduce.ewma_vol(r[:11]))
    from em_macro import tstrend
    assert (reproduce.TSMOM_K, reproduce.EWMA_COM_MONTHS, reproduce.EWMA_MIN_MONTHS, reproduce.SLEEVE_TARGET_VOL) == \
        (tstrend.TSMOM_K, tstrend.EWMA_COM_MONTHS, tstrend.EWMA_MIN_MONTHS, tstrend.SLEEVE_TARGET_VOL)


@pytest.fixture(scope="module")
def result():
    return reproduce.run(record=False)


def test_carry_reproduces_the_frozen_benchmark(result):
    assert result["window"] == {"start": "2005-01-03", "end": "2019-12-31", "role": "exploration"}
    assert set(result["carry"]) == set(fx.CURRENCIES) | {"EW"}
    for c, v in result["carry"].items():
        assert v["frozen_code_vs_file_max_abs"] < 5e-6, c              # the committed file is what the frozen code gives
        for ref in ("vs_frozen_code", "vs_committed_file"):
            x = v[ref]
            assert x["months"] >= 173 and x["corr"] >= reproduce.TOL["carry_corr_min"], (c, ref, x)
            assert x["mean_abs_diff"] <= reproduce.TOL["carry_mean_abs_max"], (c, ref, x)
            assert abs(x["sharpe_engine"] - x["sharpe_reference"]) < 0.01
    assert result["reproduced"] == {"carry": True, "trend": True}


def test_the_trend_sleeve_reproduces_the_frozen_signal(result):
    t = result["trend"]
    assert t["weights"]["months_compared"] >= 170 and t["weights"]["months_with_a_position"] >= 160
    assert t["weights"]["max_abs_diff"] <= reproduce.TOL["trend_weight_abs_max"]
    assert t["returns"]["corr"] >= reproduce.TOL["trend_return_corr_min"]
    assert t["returns"]["mean_abs_diff"] <= reproduce.TOL["trend_return_mean_abs_max"]


def test_a_recorded_run_writes_a_ledger_a_variant_log_and_a_report_and_a_second_run_adds_no_look(tmp_path, monkeypatch):
    import csv
    from nightshift import logs
    monkeypatch.setattr(logs, "main_cutoff", lambda: date(2019, 12, 31))
    assert reproduce.main(["--out", str(tmp_path)]) == 0
    led = L.Ledger(tmp_path / "exploration_ledger.jsonl", writer="session", protocol="x")
    recs = led.records("evaluation")
    assert len(recs) == 8 and L.verify(led.path) == []                 # six currencies, the basket, the trend sleeve
    assert all(r["payload"]["role"] == "exploration" and r["payload"]["evidential_weight"] == 0 for r in recs)
    assert all(r["payload"]["window"]["end"] == "2019-12-31" for r in recs)
    rows = list(csv.DictReader((tmp_path / "exploration_log.csv").open()))
    assert [r["code_ref"] for r in rows] == [r["hash"] for r in recs] and all(r["data_end"] == "2019-12-31" for r in rows)
    text = (tmp_path / "REPRODUCTION.md").read_text(encoding="utf-8")
    assert text.count("**reproduced**") == 2 and "NOT reproduced" not in text and "ETHAN_ACTIONS.md item 20" in text
    assert reproduce.main(["--out", str(tmp_path)]) == 0
    led = L.Ledger(tmp_path / "exploration_ledger.jsonl", writer="session", protocol="x")
    assert len(led.records("rerun")) == 8 and led.looks() == 8 and not led.records("nondeterminism")
    assert len(list(csv.DictReader((tmp_path / "exploration_log.csv").open()))) == 8
