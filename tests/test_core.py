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


def test_repricing_window_drops_first_round_result_day():
    from em_macro.repricing import _window
    d = _window(pd.Timestamp("2026-10-04"), pd.Timestamp("2026-10-25"))
    assert pd.Timestamp("2026-10-05") not in d          # round-1 result day
    assert pd.Timestamp("2026-10-02") in d and d[-1] == pd.Timestamp("2026-10-23")
    assert d[0] >= pd.Timestamp("2026-10-04") - pd.Timedelta(days=183)


def test_poll_average_latest_per_pollster_and_release_lag():
    from em_macro.repricing import poll_average
    polls = pd.DataFrame({"pollster": ["A", "A", "B"],
                          "field_end": pd.to_datetime(["2022-01-03", "2022-01-10", "2022-01-05"]),
                          "published": pd.to_datetime([None, None, "2022-01-07"]),
                          "a_pct": [50, 54, 48], "b_pct": [40, 40, 44]})
    days = pd.bdate_range("2022-01-04", "2022-01-12")
    s = poll_average(polls, days)
    assert s[pd.Timestamp("2022-01-04")] == 10                  # A's first poll released 01-04
    assert s[pd.Timestamp("2022-01-07")] == (10 + 4) / 2        # B released 01-07
    assert s[pd.Timestamp("2022-01-11")] == (14 + 4) / 2        # A's newer poll replaces the old


def test_ridge_tends_to_ols_and_shrinks():
    from em_macro.risk_model import _ridge
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 3))
    y = X @ np.array([1.0, -2.0, 0.5]) + rng.normal(scale=0.1, size=200)
    ols = np.linalg.lstsq(X, y, rcond=None)[0]
    assert np.allclose(_ridge(X, y, 1e-9), ols, atol=1e-6)
    assert np.linalg.norm(_ridge(X, y, 1e4)) < np.linalg.norm(ols)


def test_driscoll_kraay_zero_lags_is_time_clustered_sandwich():
    from em_macro.risk_model import _driscoll_kraay
    rng = np.random.default_rng(1)
    X = rng.normal(size=(60, 2))
    e = rng.normal(size=60)
    month = np.repeat(np.arange(20), 3)
    h = pd.DataFrame(X * e[:, None]).groupby(month).sum().values
    A = np.linalg.inv(X.T @ X + 2.0 * np.eye(2))
    assert np.allclose(_driscoll_kraay(X, e, month, 2.0, lags=0), A @ (h.T @ h) @ A)


def test_annual_values_enter_with_twelve_month_lag():
    from em_macro.risk_model import _annual_prev_year, COUNTRIES
    ann = pd.DataFrame({c: [1.0, 2.0] for c in COUNTRIES}, index=[2010, 2011])
    m = pd.period_range("2011-01", "2012-12", freq="M")
    out = _annual_prev_year(ann, m)
    assert out.loc[pd.Period("2011-06", "M"), "BR"] == 1.0      # 2010 value used during 2011
    assert out.loc[pd.Period("2012-01", "M"), "BR"] == 2.0      # 2011 value from Jan 2012
