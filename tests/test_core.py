import numpy as np
import pandas as pd
import pytest

from em_macro import carry, event_study as ES
from em_macro.build_data import clean_spikes
from em_macro.yields import mbono_ytm


def test_mbono_par_bond_yields_its_coupon():
    # a bond priced at par on a coupon date yields its coupon rate
    assert mbono_ytm(100.0, 8.0, 182 * 20) == pytest.approx(8.0, abs=1e-6)


def test_mbono_price_yield_monotone():
    assert mbono_ytm(95.0, 8.0, 3000) > mbono_ytm(100.0, 8.0, 3000) > mbono_ytm(105.0, 8.0, 3000)


def test_window_dates_sunday_election():
    bdays = pd.bdate_range("2022-01-01", "2023-01-31")
    w = ES.window_dates("2022-10-30", bdays)          # Sunday
    assert w["base"] == pd.Timestamp("2022-10-28")     # Friday
    assert w[1] == pd.Timestamp("2022-10-31")          # Monday
    assert w[5] == pd.Timestamp("2022-11-04")


def test_window_dates_weekday_announcement():
    bdays = pd.bdate_range("2022-01-01", "2023-01-31")
    w = ES.window_dates("2022-03-16", bdays)          # Wednesday decision
    assert w["base"] == pd.Timestamp("2022-03-15")
    assert w[1] == pd.Timestamp("2022-03-17")


def test_clean_spikes_removes_reversed_tick_keeps_crash():
    idx = pd.bdate_range("2020-01-01", periods=8)
    s = pd.Series([10, 10, 13, 10, 10, 13, 13, 13.0], index=idx)   # tick at 2, permanent jump at 5
    out, n = clean_spikes(s)
    assert n == 1 and np.isnan(out.iloc[2]) and out.iloc[5] == 13


def test_carry_return_formula():
    idx = pd.bdate_range("2010-01-01", "2010-03-31")
    panel = pd.DataFrame(index=idx)
    for c in carry.COUNTRIES:
        panel[f"FX_{c}"] = 2.0
        panel[f"POL_{c}"] = 12.0
    panel["US_FF"] = 0.0
    panel.loc["2010-02-01":, "FX_BR"] = 2.2       # BRL loses 1/1.1 - 1 in February
    r = carry.carry_returns(panel)
    feb_days = 28 / 365
    assert r.loc["2010-02", "BR"] == pytest.approx(2.0 / 2.2 * (1 + 0.12 * feb_days) - 1 - carry.COST)
    assert r.loc["2010-02", "MX"] == pytest.approx(0.12 * feb_days - carry.COST)


def test_stats_drawdown():
    r = pd.Series([0.1, -0.5, 0.2, 0.0, 0.0, 0.0],
                  index=pd.period_range("2010-01", periods=6, freq="M"))
    assert carry.stats(r)["max_drawdown_%"] == pytest.approx(-50.0)
