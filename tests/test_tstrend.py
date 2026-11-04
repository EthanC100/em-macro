"""Unit tests for trial T01 (em_macro/tstrend.py, em_macro/t01.py, em_macro/holdout.py)."""
import hashlib

import numpy as np
import pandas as pd
import pytest

from em_macro import holdout as HO
from em_macro import systematic as SY
from em_macro import t01 as T
from em_macro import tstrend as TS
from em_macro.config import ROOT

MONTHS = pd.period_range("2005-01", "2012-12", freq="M")


def _toy_inputs(seed=0):
    """Synthetic inputs with v1.0's structure (FX and bond books, carry/value signals, costs)."""
    rng = np.random.default_rng(seed)
    out = {"months": MONTHS}
    cost = {}
    for b, names in (("fx", ["F1", "F2", "F3", "F4", "F5", "F6"]), ("bond", ["B1", "B2", "B3", "B4", "B5"])):
        n = len(names)
        ret = pd.DataFrame(rng.normal(0.002, 0.03, (len(MONTHS), n)), index=MONTHS, columns=names)
        ret.iloc[0] = np.nan
        carry = pd.DataFrame(rng.normal(0, 1, (len(MONTHS), n)), index=MONTHS, columns=names).cumsum() * 0.1
        value = pd.DataFrame(rng.normal(0, 1, (len(MONTHS), n)), index=MONTHS, columns=names)
        out[b] = {"ret": ret, "carry": carry, "value": value}
        cost.update({k: 0.001 * (1 + i % 3) for i, k in enumerate(names)})
    out["cost"] = cost
    return out


# ------------------------------------------------------------------ TSMOM
def test_tsmom_constant_returns_matches_hand_calculation():
    r = pd.DataFrame({"x": np.full(24, 0.01)})
    sigma = pd.DataFrame({"x": np.full(24, 0.12)})
    tr = TS.tsmom(r, sigma)
    parts = [min(max(0.01 * k / (0.12 * np.sqrt(k / 12)), -2), 2) / 2 for k in (1, 3, 6, 12)]
    # k=1: 0.1443, k=3: 0.25, k=6: 0.3536, k=12: 0.5
    assert parts == pytest.approx([0.144338, 0.25, 0.353553, 0.5], abs=1e-6)
    assert tr["x"].iloc[:11].isna().all()                 # needs 12 complete months
    assert tr["x"].iloc[11] == pytest.approx(np.mean(parts))
    assert tr["x"].iloc[11] == pytest.approx(0.311973, abs=1e-6)


def test_tsmom_clips_each_horizon_and_is_antisymmetric():
    r = pd.DataFrame({"up": np.full(15, 0.20), "down": np.full(15, -0.20)})
    sigma = pd.DataFrame({"up": np.full(15, 0.10), "down": np.full(15, 0.10)})
    tr = TS.tsmom(r, sigma)
    assert tr["up"].iloc[-1] == pytest.approx(1.0)        # every horizon clipped at +2, /2 = +1
    assert tr["down"].iloc[-1] == pytest.approx(-1.0)


def test_tsmom_mixed_signs_on_toy_series():
    # 11 months of +1% then one month of -6%: k=1 negative, k=12 positive
    r = pd.DataFrame({"x": [0.01] * 11 + [-0.06]})
    sigma = pd.DataFrame({"x": [0.12] * 12})
    s = {1: -0.06, 3: -0.04, 6: -0.01, 12: 0.05}
    exp = np.mean([np.clip(s[k] / (0.12 * np.sqrt(k / 12)), -2, 2) / 2 for k in (1, 3, 6, 12)])
    assert TS.tsmom(r, sigma)["x"].iloc[-1] == pytest.approx(exp)


def test_tsmom_needs_all_windows_and_positive_sigma():
    r = pd.DataFrame({"x": [0.01] * 5 + [np.nan] + [0.01] * 12})
    sigma = pd.DataFrame({"x": [0.1] * 17 + [0.0]})
    tr = TS.tsmom(r, sigma)["x"]
    assert tr.iloc[:17].isna().all()                      # the gap at month 6 blocks every 12-month window
    assert np.isnan(tr.iloc[17])                          # sigma = 0 -> no signal


def test_ewma_vol_centre_of_mass_60_trading_days():
    rng = np.random.default_rng(1)
    x = pd.Series(rng.normal(0, 0.03, 40))
    v = TS.ewma_vol(x.to_frame("x"))["x"]
    com = 60 / 21
    a = 1 / (1 + com)                                     # decay lambda = com / (1 + com) = 0.7407
    assert 1 - a == pytest.approx(0.740741, abs=1e-6)
    t = 30
    w = (1 - a) ** np.arange(t, -1, -1)
    xs = x.iloc[: t + 1].values
    mu = (w * xs).sum() / w.sum()
    var = (w * (xs - mu) ** 2).sum() / w.sum() / (1 - (w ** 2).sum() / w.sum() ** 2)
    assert v.iloc[t] == pytest.approx(np.sqrt(var) * np.sqrt(12))
    assert v.iloc[:11].isna().all() and v.iloc[11:].notna().all()   # at least 12 months


def test_trend_raw_weights_divide_by_n_active():
    rng = np.random.default_rng(5)
    r = pd.DataFrame({"a": 0.01 + rng.normal(0, 0.02, 14), "b": -0.02 + rng.normal(0, 0.02, 14),
                      "c": [np.nan] * 10 + [0.01] * 4})
    w = TS.trend_raw_weights(r)
    sigma = TS.ewma_vol(r)
    trend = TS.tsmom(r, sigma)
    t = 13
    assert w["c"].iloc[t] == 0.0                          # c inactive (fewer than 12 returns)
    for k in ("a", "b"):
        assert w[k].iloc[t] == pytest.approx(trend[k].iloc[t] * 0.10 / sigma[k].iloc[t] / 2)
    assert w.iloc[:11].abs().sum().sum() == 0.0


# ------------------------------------------------------------------ risk budget and scaling
def test_risk_budget_split_is_80_20_and_scales_to_target():
    inp = _toy_inputs()
    R = TS.all_returns(inp)
    core = TS.core_targets(inp)
    trend = TS.trend_targets(inp)
    m = TS.mix(core, trend)
    assert TS.RISK_BUDGET == {"core": 0.80, "trend": 0.20}
    pd.testing.assert_frame_equal(m, 0.8 * core + 0.2 * trend)
    pd.testing.assert_frame_equal(TS.mix(core, trend, 1.0), core)
    # each sleeve and the total run at 10% pro-forma (trailing 36 months) vol once enough history exists
    tot = TS.scale_to_vol(m, R)
    for W in (core, trend, tot):
        t = MONTHS[60]
        hist = R.loc[:t].iloc[-36:].fillna(0.0)
        assert (hist @ W.loc[t]).std() * np.sqrt(12) == pytest.approx(0.10)


def test_trend_has_20pct_risk_share_when_sleeves_are_uncorrelated():
    # two sleeves on disjoint, independent instruments, each at unit scale: weights 0.8 / 0.2 of vol
    idx = pd.period_range("2000-01", periods=48, freq="M")
    rng = np.random.default_rng(3)
    R = pd.DataFrame(rng.normal(0, 0.03, (48, 2)), index=idx, columns=["c", "t"])
    core = TS.scale_to_vol(pd.DataFrame({"c": 1.0, "t": 0.0}, index=idx), R)
    trend = TS.scale_to_vol(pd.DataFrame({"c": 0.0, "t": 1.0}, index=idx), R)
    m = TS.mix(core, trend).iloc[-1]
    hist = R.iloc[-36:]
    vc, vt = hist["c"].std() * m["c"], hist["t"].std() * m["t"]
    assert vc / (vc + vt) == pytest.approx(0.8)


def test_finish_reproduces_v1_run_exactly_on_toy_inputs():
    inp = _toy_inputs(2)
    for use in (["carry", "trend", "value"], ["carry", "value"], ["carry"]):
        a = SY.run(inp, use)
        b = TS.finish(inp, TS.core_targets(inp, use))
        pd.testing.assert_frame_equal(a, b)
        pd.testing.assert_frame_equal(a.attrs["weights"], b.attrs["weights"])


def test_run_t01_core_sleeve_equals_v1_carry_value_and_costs_double():
    inp = _toy_inputs(4)
    res = TS.run_t01(inp)
    pd.testing.assert_frame_equal(res["core sleeve"], SY.run(inp, ["carry", "value"]))
    res2 = TS.run_t01(TS.with_costs(inp, 2.0))
    pd.testing.assert_series_equal(res2["T01"]["cost"], 2 * res["T01"]["cost"])
    pd.testing.assert_series_equal(res2["T01"]["gross"], res["T01"]["gross"])


def test_subset_keeps_only_listed_instruments():
    inp = _toy_inputs()
    s = TS.subset(inp, ["F1", "F3", "F5", "B2", "B3", "B4"])
    assert list(s["fx"]["ret"].columns) == ["F1", "F3", "F5"]
    assert list(s["bond"]["value"].columns) == ["B2", "B3", "B4"]
    assert list(inp["fx"]["ret"].columns) == ["F1", "F2", "F3", "F4", "F5", "F6"]   # original untouched


# ------------------------------------------------------------------ holdout split
def test_holdout_split_is_fixed_balanced_and_stratified():
    s = HO.split()
    assert sorted(u for u, h in s.items() if h == "B") == ["BR", "CO", "FR", "GB", "IT", "TR", "ZA"]
    assert sum(h == "A" for h in s.values()) == 7
    for st in HO.STRATA:
        members = [u for u, (x, _) in HO.UNITS.items() if x == st]
        nb = sum(s[u] == "B" for u in members)
        assert abs(2 * nb - len(members)) <= 1
    ins = HO.instruments("A") + HO.instruments("B")
    assert len(ins) == 23 and len(set(ins)) == 23


# ------------------------------------------------------------------ statistics
def test_expected_shortfall_acerbi_tasche():
    r = pd.Series(np.arange(1, 82, dtype=float) / 100 - 0.2)  # 81 months, worst = -0.19, -0.18, -0.17
    m = 0.025 * 81
    exp = -(-0.19 - 0.18 + (m - 2) * -0.17) / m
    assert T.expected_shortfall(r) == pytest.approx(exp)


def test_block_bootstrap_p_value_behaviour():
    rng = np.random.default_rng(0)
    base = pd.Series(rng.normal(0.005, 0.03, 81))
    better = base + 0.01
    p_better = T.bootstrap_delta_sharpe(better, base, B=2000)["p_one_sided"]
    p_same = T.bootstrap_delta_sharpe(base + rng.normal(0, 1e-4, 81), base, B=2000)["p_one_sided"]
    assert p_better < 0.01
    assert 0.1 < p_same < 0.9


def test_circular_block_indices():
    idx = T.circular_block_indices(10, 6, np.random.default_rng(0))
    assert len(idx) == 10
    d = np.diff(idx[:6]) % 10
    assert (d == 1).all()                                 # first block is 6 consecutive (circular) months


# ------------------------------------------------------------------ v1.0 untouched
# Code and frozen results must still match docs/v1.0_freeze.md byte for byte.  The two data
# panels are rebuilt and committed by the monthly workflow (systematic.yml), so they cannot be
# pinned whole: for daily_panel.csv the rows of the frozen sample (before 2026-10) are hashed;
# country_month_panel.csv is not hashed, because its latest-vintage annual series (IMF WEO,
# World Bank, ratings) are re-assigned to every month of the year and change with each refresh.
# The panels exactly as they were at the freeze are at commit 7886867 (docs/v1.0_freeze.md).
V1_HASHES = {
    "em_macro/systematic.py": "1eb4cf6b1c537c1711e5fff0b7aa044fee932c20992eb0d3cea4c3c5fc50be66",
    "results/systematic/fit/frozen_design.json": "f0cce4c9a819379c7bce4310ad58e8765b8149ef0d045ab25dd84c1b13983858",
    "results/systematic/test/performance_2020_on.csv":
        "1f8828109a6ab741993f2f49947320cc2a87c66abb308d3d37684151175087ed",
    "em_macro/risk_model.py": "2000a49747a2fba4064efe25a7eaf107e14b484ded7e5534f068a81b73738e74",
}
V1_FROZEN_ROWS = {   # path: (first date outside the frozen sample, sha256 of header + earlier rows)
    "data/processed/daily_panel.csv": ("2026-10-01", "9b30b9f62be92efa75414178800abc322aa47fd03393f307b1e8e2ca2d79fc79"),
}


@pytest.mark.parametrize("path,sha", sorted(V1_HASHES.items()))
def test_v1_frozen_files_unchanged(path, sha):
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha


@pytest.mark.parametrize("path,cutoff,sha", [(k, *v) for k, v in sorted(V1_FROZEN_ROWS.items())])
def test_v1_frozen_sample_rows_unchanged(path, cutoff, sha):
    lines = (ROOT / path).read_text().splitlines(keepends=True)
    kept = lines[:1] + [l for l in lines[1:] if l[:len(cutoff)] < cutoff]
    assert hashlib.sha256("".join(kept).encode()).hexdigest() == sha


def test_turnover_times_uniform_cost_equals_cost():
    inp = _toy_inputs(6)
    inp["cost"] = {k: 0.002 for k in inp["cost"]}
    # the toy names are not v1.0's, so map them to v1.0 FX names for the book split
    ren = dict(zip(["F1", "F2", "F3", "F4", "F5", "F6"], ["BRL", "MXN", "ZAR", "TRY", "IDR", "PLN"]))
    inp["fx"] = {k: v.rename(columns=ren) for k, v in inp["fx"].items()}
    inp["cost"] = {ren.get(k, k): v for k, v in inp["cost"].items()}
    res = TS.run_t01(inp)["T01"]
    pd.testing.assert_series_equal(T.turnover(res) * 0.002, res["cost"], check_names=False)
