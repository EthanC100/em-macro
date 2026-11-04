"""Unit tests for the T16-T19 risk batch (em_macro/t16_crash.py, t17_factorcap.py, t18_rebal.py, t19_vol.py,
t1619.py).  Synthetic inputs only: each trial must reproduce frozen v1.0 exactly when its one change is
switched off, and the statistics must match hand calculations."""
import numpy as np
import pandas as pd
import pytest

from em_macro import systematic as SY
from em_macro import t16_crash as T16
from em_macro import t17_factorcap as T17
from em_macro import t18_rebal as T18
from em_macro import t19_vol as T19
from em_macro import t1619 as B

from test_tstrend import _toy_inputs

V1 = ["carry", "trend", "value"]


@pytest.fixture(scope="module")
def inp():
    return _toy_inputs(1)


@pytest.fixture(scope="module")
def v1(inp):
    return SY.run(inp, V1)


# ------------------------------------------------------------------ T18
def test_t18_with_no_band_and_full_trades_equals_v1_without_band(inp):
    nb = SY.run(inp, V1, band=0)
    r, _ = T18.run(inp, band=0.0, partial=1.0)
    assert (r["net"] - nb["net"]).abs().max() < 1e-15


def test_t18_pnl_path_on_v1_band_weights_equals_v1(inp, v1):
    held = SY._apply_band(T18.capped_targets(inp), SY.DESIGN["no_trade_band"])
    assert (T18.pnl(inp, held)["net"] - v1["net"]).abs().max() == 0.0


def test_t18_rules_hand_calculation():
    months = pd.period_range("2020-01", "2020-04", freq="M")
    tgt = pd.DataFrame({"X": [1.0, 1.0, 0.0, 0.0], "Y": [1.0, 1.0, 1.0, 1.0]}, index=months)
    sig = pd.DataFrame({"X": [0.10] * 4, "Y": [0.10] * 4}, index=months)
    held, log = T18.apply_rules(tgt, sig, {"X": "fx", "Y": "fx"}, band=0.1, partial=0.5)
    # budget = mean |w*| sigma of the selected positions = 0.1; band threshold 0.01 of risk = 0.1 of weight
    assert held.loc["2020-01", "X"] == 0.5 and held.loc["2020-02", "X"] == 0.75   # half-trades of 0.5, 0.25 clear the band
    # 2020-03: target 0, half-trade -0.375 (risk 0.0375 > 0.01): trades to 0.375
    assert held.loc["2020-03", "X"] == pytest.approx(0.375)
    # 2020-04: half-trade -0.1875 (risk 0.01875 > 0.01) -> 0.1875
    assert held.loc["2020-04", "X"] == pytest.approx(0.1875)
    # Y builds up 0.5, 0.75, 0.875, then the half-trade 0.0625 (risk 0.00625 <= 0.01) is inside the band: stays
    assert list(held["Y"].round(6)) == [0.5, 0.75, 0.875, 0.875]
    assert (~log[(log.instrument == "Y") & (log.month == "2020-04")]["traded"]).all()


def test_t18_residual_of_exited_position_is_closed():
    months = pd.period_range("2020-01", "2020-03", freq="M")
    tgt = pd.DataFrame({"X": [1.0, 0.0, 0.0], "Y": [1.0, 1.0, 1.0]}, index=months)
    sig = pd.DataFrame({"X": [0.10] * 3, "Y": [0.10] * 3}, index=months)
    held, _ = T18.apply_rules(tgt, sig, {"X": "fx", "Y": "fx"}, band=10.0, partial=0.5)   # a band nothing clears
    # with an uncleared band the entry of X never trades (0); make X held by hand: use partial 1 first month
    held2, _ = T18.apply_rules(tgt, sig, {"X": "fx", "Y": "fx"}, band=0.0, partial=1.0)
    assert held2.loc["2020-02", "X"] == 0.0
    # residual rule: held 0.1 with target 0 and a band it cannot clear is closed, not kept
    tgt2 = pd.DataFrame({"X": [0.1, 0.0], "Y": [1.0, 1.0]}, index=months[:2])
    sig2 = sig.iloc[:2]
    h, log = T18.apply_rules(tgt2, sig2, {"X": "fx", "Y": "fx"}, band=0.1, partial=0.5)
    assert h.loc["2020-02", "X"] == 0.0 and log[(log.instrument == "X") & (log.month == "2020-02")]["traded"].all()


# ------------------------------------------------------------------ T19
def test_t19_with_v1_estimator_equals_v1(inp, v1):
    r = T19.run(inp, vol_fn=T19.v1_vol_fn)
    assert (r["net"] - v1["net"]).abs().max() < 1e-15


def test_t19_vol_est_is_floored_ewma():
    x = pd.Series(np.r_[np.full(60, 0.03), np.full(24, 0.005)])
    s, l = T19.ewma_sigma(x, T19.HL_SHORT_MONTHS), T19.ewma_sigma(x, T19.HL_LONG_MONTHS)
    v = T19.vol_est(x)
    assert v.iloc[-1] == pytest.approx(max(s.iloc[-1], 0.8 * l.iloc[-1]))
    assert v.iloc[-1] > s.iloc[-1]           # after a calm spell the long-run floor binds
    assert v.iloc[:11].isna().all() and v.iloc[11:].notna().all()
    # constant returns: both EWMAs equal |x| sqrt(12), the floor does not bind
    c = pd.Series(np.full(50, 0.02))
    assert T19.vol_est(c).iloc[-1] == pytest.approx(0.02 * np.sqrt(12))
    assert not T19.floor_binds(c).iloc[-1]


# ------------------------------------------------------------------ T17
def _factors(inp, seed=3):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"USD": rng.normal(0, 0.02, len(inp["months"])),
                         "EM": inp["fx"]["ret"][["F1", "F2", "F3"]].mean(axis=1)}, index=inp["months"])


def test_t17_with_caps_that_never_bind_equals_v1(inp, v1):
    r, log = T17.run(inp, _factors(inp), caps={"USD": 10.0, "EM": 10.0})
    assert (r["net"] - v1["net"]).abs().max() < 1e-15
    assert not log["adjusted"].any()


def test_t17_caps_are_enforced_and_minimal(inp):
    r, log = T17.run(inp, _factors(inp), caps={"USD": 0.05, "EM": 0.05})
    m = log[log["modelled"] == True]
    assert m["adjusted"].any()
    assert (m["usd_share_after"] <= 0.05 + 1e-6).all() and (m["em_share_after"] <= 0.05 + 1e-6).all()
    # months that were already inside the caps are untouched
    inside = m[(m["usd_share_before"] <= 0.05) & (m["em_share_before"] <= 0.05)]
    assert (inside["distance"] == 0).all()


def test_t17_shares_sum_to_factor_variance_share_for_pure_factor_position():
    rng = np.random.default_rng(0)
    F = rng.normal(0, 0.02, (120, 2))
    R = np.column_stack([F[:, 0] * 1.0 + rng.normal(0, 1e-4, 120), F[:, 1] * 0.5 + rng.normal(0, 1e-4, 120)])
    rm = T17.RiskModel(R, F)
    s = rm.shares(np.array([1.0, 0.0]))
    assert s[0] == pytest.approx(1.0, abs=0.15) and abs(s[1]) < 0.1     # shrinkage understates it slightly


# ------------------------------------------------------------------ T16
def test_t16_with_scale_one_equals_v1(inp, v1):
    sc = pd.DataFrame(1.0, index=inp["months"], columns=inp["fx"]["ret"].columns)
    assert (T16.run(inp, sc)["net"] - v1["net"]).abs().max() == 0.0


def test_t16_scale_applies_to_long_currencies_only(inp):
    sc = pd.DataFrame(0.5, index=inp["months"], columns=inp["fx"]["ret"].columns)
    W0 = T16.targets(inp, pd.DataFrame(1.0, index=inp["months"], columns=inp["fx"]["ret"].columns))
    W = T16.targets(inp, sc)
    fx, bd = list(inp["fx"]["ret"].columns), list(inp["bond"]["ret"].columns)
    assert (W[bd] == W0[bd]).all().all()
    longs = W0[fx] > 0
    assert np.allclose(W[fx].where(longs), (0.5 * W0[fx]).where(longs), equal_nan=True)
    assert np.allclose(W[fx].where(~longs), W0[fx].where(~longs), equal_nan=True)


def test_t16_labels_hand_calculation():
    months = pd.period_range("2010-01", "2014-12", freq="M")
    r = pd.DataFrame({"A": np.full(60, 0.01)}, index=months)
    r.loc["2013-02", "A"] = -0.20                 # one crash month
    lab = T16.labels(r)
    sigma = SY._vol(r)
    thr = -2.0 * sigma.loc["2013-01", "A"] * np.sqrt(3 / 12)
    assert thr <= 0 and lab.loc["2013-01", "A"] == 1.0
    assert lab.loc["2012-11", "A"] == 1.0 and lab.loc["2012-10", "A"] == 0.0   # 3-month horizon
    assert lab.loc["2014-11", "A"] != lab.loc["2014-11", "A"]                   # NaN: no 3 forward months


def test_t16_logistic_and_auc():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(600, 3))
    y = (X[:, 0] + 0.3 * rng.normal(size=600) > 0).astype(float)
    th = T16.fit_logistic(X, y, 1.0)
    assert th[1] > 1 and abs(th[2]) < 0.3 and abs(th[3]) < 0.3
    assert T16.auc(y, T16.predict(th, X)) > 0.9
    assert T16.auc(np.array([1, 0, 1, 0]), np.array([0.9, 0.1, 0.8, 0.2])) == 1.0
    # a stronger penalty shrinks the slope
    assert abs(T16.fit_logistic(X, y, 0.001)[1]) < abs(th[1])


def test_t16_decision_rule():
    p = pd.DataFrame({"A": [0.05, 0.10, 0.15, 0.20, np.nan]})
    pb = pd.DataFrame({"A": [0.05] * 5})
    scale = (1 - (p - pb) / (2 * pb)).clip(0, 1).where(p.notna(), 1.0)
    assert list(scale["A"]) == pytest.approx([1.0, 0.5, 0.0, 0.0, 1.0])


def test_t16_walk_forward_uses_only_past_labels():
    months = pd.period_range("2005-01", "2012-12", freq="M")
    rng = np.random.default_rng(1)
    idx = pd.MultiIndex.from_product([months, ["A", "B"]], names=["month", "currency"])
    feat = pd.DataFrame(rng.normal(size=(len(idx), len(T16.FEATURES))), index=idx, columns=T16.FEATURES)
    lab = pd.DataFrame((rng.random((len(months), 2)) < 0.1).astype(float), index=months, columns=["A", "B"])
    lab.iloc[-3:] = np.nan
    out = T16.walk_forward(feat, lab, ["A", "B"], ["A", "B"], first_year=2011, last_year=2012)
    ys = {y["year"]: y for y in out["years"]}
    assert ys[2011]["fitted"] and ys[2012]["fitted"]
    assert ys[2011]["n_train"] == 2 * len(months[months <= pd.Period("2010-09", "M")])
    assert out["p"].loc["2011-01":"2012-12"].notna().all().all() and out["p"].loc[:"2010-12"].isna().all().all()
    assert (out["scale"].loc[:"2010-12"] == 1.0).all().all()
    assert out["scale"].min().min() >= 0 and out["scale"].max().max() <= 1


# ------------------------------------------------------------------ statistics
def test_holm_adjustment():
    adj = B.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.5})
    assert adj["a"] == pytest.approx(0.04) and adj["c"] == pytest.approx(0.09)
    assert adj["b"] == pytest.approx(0.09) and adj["d"] == pytest.approx(0.5)
    adj = B.holm({"a": 0.02, "b": 0.02})
    assert adj == {"a": 0.04, "b": 0.04}


def test_bootstrap_noninferiority_margin_shifts_the_null():
    rng = np.random.default_rng(5)
    idx = pd.period_range("2020-01", "2026-09", freq="M")
    b = pd.Series(rng.normal(0.005, 0.03, 81), index=idx)
    a = b + rng.normal(0, 0.002, 81)
    r = B.bootstrap_noninferiority(a, b, margin=0.05, B=400)
    assert r["p_one_sided"] <= r["p_one_sided_margin0"]      # H1 dSR > -0.05 is easier than dSR > 0
    r0 = B.bootstrap_noninferiority(a, b, margin=0.0, B=400)
    assert r0["p_one_sided"] == pytest.approx(r["p_one_sided_margin0"])


def test_by_year_matches_annual_compounding():
    idx = pd.period_range("2020-01", "2021-12", freq="M")
    r = pd.Series(0.01, index=idx)
    res = pd.DataFrame({"net": r, "cost": 0.0, "gross_leverage": 1.0}, index=idx)
    W = pd.DataFrame({"BRL": 1.0, "DE10Y": 1.0}, index=idx)
    res.attrs["weights"] = W
    t = B.by_year(res, idx[0], idx[-1])
    assert list(t["year"]) == [2020, 2021] and t["return_%"].iloc[0] == pytest.approx(100 * (1.01 ** 12 - 1))
