"""Tests for the T02 economic-momentum signal construction (synthetic data; no downloads)."""
import numpy as np
import pandas as pd

from em_macro import econmom as EM


def _s(values, start="2010-01"):
    return pd.Series(values, index=pd.period_range(start, periods=len(values), freq="M"), dtype=float)


def test_index_is_chain_linked_mean_growth_with_inverse_unemployment():
    ip = _s([100, 102, 102])
    u = _s([5.0, 5.0, 4.0])                      # 1/U growth in month 3: 5/4 - 1 = 25%
    fi = EM.fundamental_index({"IP": ip, "U": u}, "econ")
    assert fi.index[0] == pd.Period("2010-01", "M") and fi.iloc[0] == 100
    assert np.isclose(fi.iloc[1], 100 * (1 + (0.02 + 0.0) / 2))
    assert np.isclose(fi.iloc[2], fi.iloc[1] * (1 + (0.0 + 0.25) / 2))


def test_missing_component_left_out_of_average():
    ip = _s([100, 110, 121])
    rs = _s([50, 55])                            # ends a month earlier
    fi = EM.fundamental_index({"IP": ip, "RS": rs}, "econ")
    assert np.isclose(fi.iloc[2] / fi.iloc[1], 1.10)   # only IP in month 3
    assert fi.index.max() == pd.Period("2010-03", "M")


def test_chain_breaks_at_a_month_without_any_growth():
    ip = pd.concat([_s([100, 101], "2010-01"), _s([200, 202, 204], "2010-05")])
    fi = EM.fundamental_index({"IP": ip}, "econ")
    assert fi.index.min() == pd.Period("2010-05", "M")  # the run after the gap; base = first month of the run


def test_trends_log_change_over_lookbacks():
    fi = pd.Series([100.0, 110.0, 121.0], index=pd.period_range("2010-01", periods=3, freq="M"))
    z = EM.trends(fi)
    assert np.isclose(z[1], np.log(121 / 110)) and np.isclose(z[2], np.log(121 / 100)) and np.isnan(z[3])


def test_score_ranks_demeaned_and_minimums():
    idx = pd.MultiIndex.from_tuples([("econ", l) for l in range(1, 13)] + [("infl", 1)])
    z = pd.DataFrame({"A": 1.0, "B": 2.0, "C": 3.0, "D": np.nan}, index=idx)
    z.loc[("infl", 1)] = [1.0, np.nan, np.nan, 5.0]     # only 2 currencies: sub-signal does not exist
    s = EM.score_from_z(z)
    assert np.isclose(s["A"], -1) and np.isclose(s["B"], 0) and np.isclose(s["C"], 1)
    assert np.isnan(s["D"])                              # fewer than 12 sub-signals


def test_quarterly_carried_to_the_quarter_months():
    q = pd.Series([5.0, 6.0], index=pd.PeriodIndex(["2013-01", "2013-04"], freq="M"))
    m = EM.quarterly_to_monthly(q)
    assert list(m.values) == [5, 5, 5, 6, 6, 6] and m.index[-1] == pd.Period("2013-06", "M")


def test_source_plan_covers_every_country_and_component():
    for area in EM.CCY_AREA.values():
        for c in EM.COMPONENTS:
            segs = EM.SOURCE_PLAN[area][c]
            for a, b in zip(segs, segs[1:]):
                assert b.start == a.end + 1, (area, c)
