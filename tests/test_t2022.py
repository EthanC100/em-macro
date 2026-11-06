"""Synthetic tests for the T20-T22 trial machinery (em_macro/t2022.py).  No real data: toy contracts and the toy
v1.0 inputs of test_tstrend."""
import numpy as np
import pandas as pd
import pytest

from em_macro import commod_data as CD
from em_macro import t18_rebal as T18
from em_macro import t2022 as T
from test_commod_data import _write_contract
from test_tstrend import _toy_inputs


@pytest.fixture()
def toy_mkt(tmp_path, monkeypatch):
    folder = tmp_path / "norgate" / CD.SNAPSHOT / "contracts" / "CL"
    folder.mkdir(parents=True)
    for y in (2019, 2020, 2021):
        for code in CD.MONTH_CODES:
            _write_contract(folder, f"CL-{y}{code}", "2018-01-02", "2021-06-30")
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path))
    return T.Mkt("CL", pd.DataFrame(columns=["EUR", "GBP"]))


def test_sleeve_daily_pnl_matches_hand_calculation(toy_mkt):
    mk = toy_mkt
    months = mk.rolls.index
    sl = object.__new__(T.Sleeve)
    sl.mks = {"CL": mk}
    sl.held = pd.DataFrame({"CL": 0.0}, index=months)
    m = pd.Period("2020-03", "M")
    sl.held.loc[m, "CL"] = 2.0
    g, k, G, trades = sl._daily()
    a, b = mk.rolls.at[m, "execution"], mk.rolls.at[m + 1, "execution"]
    c = mk.rolls.at[m, "F1"]
    px = mk.md.close[c]
    expect = 2.0 * (px[b] - px[a]) / px[a]
    seg = g[(g.index > a) & (g.index <= b)]
    assert abs(seg.sum() - expect) < 1e-12
    assert (g[(g.index <= a) | (g.index > b)] == 0).all()
    # entry and exit are charged at c_raw on the traded notional
    assert abs(k[a] - 2.0 * T.Sleeve.c_raw(mk, c, a)) < 1e-15
    assert abs(k[b] - 2.0 * T.Sleeve.c_raw(mk, mk.rolls.at[m + 1, "F1"], b)) < 1e-15 or k[b] > 0


def test_c_raw_formula(toy_mkt):
    mk = toy_mkt
    m = pd.Period("2020-03", "M")
    c, a = mk.rolls.at[m, "F1"], mk.rolls.at[m, "execution"]
    F = mk.md.close.at[a, c]
    assert abs(T.Sleeve.c_raw(mk, c, a) - (3 + 1 * 10) / (F * 1000)) < 1e-15


def test_cap_risk_limits_share():
    sig = pd.Series(1.0, index=list("abcdefghijkl"))
    w = pd.Series([5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1.0], index=sig.index)
    out = T.cap_risk(w, sig)
    share = out.abs() * sig / (out.abs() * sig).sum()
    assert share.max() <= 0.10 + 1e-9
    assert (np.sign(out) == np.sign(w)).all()


def test_holm():
    assert T.holm({"a": 0.01, "b": 0.04, "c": 0.03}) == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})


def test_bootstrap_noninferiority_identical_series():
    r = pd.Series(np.random.default_rng(1).normal(0.01, 0.03, 81))
    bs = T.bootstrap(r, r, B=200)
    assert bs["delta_sr"] == 0 and bs["p_noninf"] == pytest.approx(1 / 201)


def test_nw_tstat_no_lags_is_plain_t():
    x = pd.Series(np.random.default_rng(2).normal(0.1, 1, 200))
    m, t = T.nw_tstat(x, 0)
    assert t == pytest.approx(x.mean() / (x.std(ddof=0) / np.sqrt(len(x))))


def test_combine_with_empty_sleeve_is_scaled_v11():
    inp = _toy_inputs(1)
    v11, _ = T18.run(inp)
    months = v11.attrs["weights"].index
    sl = object.__new__(T.Sleeve)
    sl.held = pd.DataFrame({"X": 0.0}, index=months)
    sl.R = pd.DataFrame({"X": 0.0}, index=months)
    sl.daily_gross = pd.Series(0.0, index=months.to_timestamp())
    sl.daily_cost1 = pd.Series(0.0, index=months.to_timestamp())
    sl.mks = {}
    sl.notional_cost_rate = lambda m: pd.Series(dtype=float)
    out = T.combine(inp, v11, sl, 1.0, 2.0)
    assert (out["sleeve_leg_net"] == 0).all()
    # v1.1 legs = 0.75 s_t W_v11 through v1.1's accounting
    W = v11.attrs["weights"]
    V = W.mul(out.attrs["scale_all"].reindex(W.index) * 0.75, axis=0)
    ref = T18.pnl(inp, V)["net"]
    assert np.allclose(out["v11_leg_net"].values, ref.reindex(out.index).values)


def _toy_market(folder, code, seed):
    """Random-walk contracts for every month 2017-2022 with a contango/backwardation term structure."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2016-01-04", "2022-06-30")
    spot = 50 * np.exp(np.cumsum(rng.normal(0, 0.015, len(days))))
    slope = rng.normal(0, 0.02)
    folder.mkdir(parents=True, exist_ok=True)
    for y in range(2017, 2023):
        for i, mc in enumerate(CD.MONTH_CODES):
            exp = pd.Timestamp(y, i + 1, 1) - pd.Timedelta(days=10)
            sel = (days >= exp - pd.Timedelta(days=500)) & (days <= exp)
            d = days[sel]
            tau = (exp - d).days / 365
            px = spot[sel] * np.exp(slope * tau)
            df = pd.DataFrame({"date": d.strftime("%Y-%m-%d"), "open": px, "high": px, "low": px, "close": px,
                               "volume": 1, "open_interest": 1})
            df.to_csv(folder / f"{CD.MARKETS[code].norgate}-{y}{mc}.csv", index=False)


def test_pipeline_end_to_end_on_synthetic_markets(tmp_path, monkeypatch):
    codes = ["CL", "HO", "RB", "NG", "SB", "GF", "HE"]          # notice = LTD markets: all 12 months usable
    for k, c in enumerate(codes):
        _toy_market(tmp_path / "norgate" / CD.SNAPSHOT / "contracts" / c, c, k)
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path))
    fx = pd.DataFrame(columns=["EUR", "GBP"])
    mks = {c: T.Mkt(c, fx) for c in codes}
    months = pd.period_range("2017-01", "2022-04", freq="M")
    sig20 = {c: T.signal_t20(mks[c], "A") for c in codes}
    sig21 = {c: T.signal_t21(mks[c]) for c in codes}
    sgm = {c: mks[c].sigma_blend() for c in codes}
    sig22 = {c: T.signal_t22(mks[c], mks[c].sigma_mop()) for c in codes}
    sleeves = {}
    for name, sg in (("T20", sig20), ("T21", sig21), ("T22", sig22)):
        W, SG = T.build_targets(mks, sg, sgm, name, months)
        sleeves[name] = T.Sleeve(name, mks, W, SG)
        assert np.isfinite(sleeves[name].monthly(2.0)).all()
    assert (sleeves["T20"].held.abs().sum(axis=1) > 0).any()
    # the risk cap holds on every T20 target month with at least 10 markets (here: never 10, so check shares <= 1)
    cw = T.clark_west(mks, sig20)
    assert set(cw) == {"2010-01..2026-09", "2020-01..2026-09"}
    # combination machinery with toy v1.0 inputs on overlapping synthetic months
    inp = _toy_inputs(1)
    v11, _ = T18.run(inp)
    out = T.combine(inp, v11, sleeves["T20"], 1.0, 2.0)
    assert np.isfinite(out["net"]).all() and "turnover" in out
    bs = T.bootstrap(out["net"].iloc[:60], T.T01._net(v11).reindex(out.index).iloc[:60].fillna(0.0), B=50)
    assert 0 < bs["p_noninf"] <= 1


def test_diagnostics_run_on_synthetic_objects(tmp_path, monkeypatch):
    codes = ["CL", "HO", "RB", "NG", "SB", "GF", "HE"]
    for k, c in enumerate(codes):
        _toy_market(tmp_path / "norgate" / CD.SNAPSHOT / "contracts" / c, c, k)
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path))
    monkeypatch.setattr(T, "TEST", (pd.Period("2019-01", "M"), pd.Period("2021-12", "M")))
    monkeypatch.setattr(T, "FULL", (pd.Period("2018-01", "M"), pd.Period("2021-12", "M")))
    monkeypatch.setattr(T, "DESIGN", (pd.Period("2018-01", "M"), pd.Period("2018-12", "M")))
    fx = pd.DataFrame(columns=["EUR", "GBP"])
    mks = {c: T.Mkt(c, fx) for c in codes}
    months = pd.period_range("2017-01", "2022-04", freq="M")
    sgm = {c: mks[c].sigma_blend() for c in codes}
    sig = {"T20": {c: T.signal_t20(mks[c], "A") for c in codes}, "T21": {c: T.signal_t21(mks[c]) for c in codes},
           "T22": {c: T.signal_t22(mks[c], mks[c].sigma_mop()) for c in codes}}
    sleeves = {}
    for t in ("T20", "T21", "T22"):
        W, SG = T.build_targets(mks, sig[t], sgm, t, months)
        sleeves[(t, "full")] = T.Sleeve(t, mks, W, SG)
    pm = pd.period_range("2016-01", "2022-06", freq="M")
    rng = np.random.default_rng(3)
    inp = {"spx": pd.Series(rng.normal(0, 0.04, len(pm)), index=pm)}
    v = pd.DataFrame({"net": rng.normal(0, 0.03, len(pm))}, index=pm)
    v.attrs["weights"] = pd.DataFrame(index=pm)
    comb = {(t, "full", "decisive"): pd.DataFrame({"net": v["net"], "kappa": 0.3}, index=pm) for t in ("T20", "T21", "T22")}
    out = T.diagnostics(inp, {1.0: v}, v, sleeves, comb, sig, mks, {c: "A" for c in codes})
    assert set(out) >= {"corr_2020_2026", "by_year_%", "rounding_10m", "t22_gross_by_asset_class_ann_%"}


def test_report_writer_on_fabricated_tables(tmp_path, monkeypatch):
    import json
    from em_macro import t2022_report as R
    out = tmp_path / "T20-T22"
    out.mkdir()
    cr = lambda n: {"#": n, "criterion": "x", "value": "1", "pass": True}
    bs = {"delta_sr": 0.01, "p_noninf": 0.02, "p_superiority": 0.3, "boot_mean": 0.0, "boot_sd": 0.1,
          "boot_q05": -0.1, "boot_q95": 0.1}
    dsr = {"N": 16, "SR_ann": 0.9, "DSR_noise": 0.7, "DSR_dispersed": 0.2}
    crit = {t: {"combined": [cr(f"C{i}") for i in range(1, 5)], "sleeve": [cr(f"S{i}") for i in range(1, 4)],
                "overall_pass": False, "bootstrap": bs, "p_holm": 0.04, "p_holm_2x": 0.05,
                "dsr": {"trial": dsr, "v1.1": dsr}} for t in ("T20", "T21", "T22")}
    crit["_extra"] = {"clark_west": {"2010-01..2026-09": {"cw_t": 1.0, "p_one_sided": 0.16, "months": 200}},
                      "t21_alpha_vs_t20": {"alpha_ann": 0.01, "alpha_t": 1.0, "beta": 0.1, "months": 300},
                      "t21_nw": {"t": 1.2}, "breakeven": {"T20": 3.0}, "carry_worst_months": ["2020-03"],
                      "dropped": ["PA"], "t22_universe": ["CL"], "option": {"CL": "A", "B": "B"}}
    (out / "criteria.json").write_text(json.dumps(crit))
    (out / "RUN.json").write_text(json.dumps({"run_started_utc": "a", "run_finished_utc": "b", "git_head_at_run": "abcdef0",
                                              "pandas": "3", "numpy": "2", "decisions": ["d1"],
                                              "reproduction": {"v1.0_identical": True, "v1.1_reproduces_T18": True}}))
    diag = {"by_year_%": {"v1.1": {"2020": 1.0}}, "corr_2020_2026": {"a": {"a": 1.0}},
            "v11_worst5": {"2020-03": {"v1.1_%": -3.0}}, "option_A_share": 0.7, "bm_carry_signal_rank_corr_mean": 0.1,
            "t20_t21_sleeve_corr_2000_2026": 0.2, "t22_gross_by_asset_class_ann_%": {"bonds": 1.0},
            "t22_net_fx_notional_mean": 0.1, "t22_net_bond_notional_mean": 0.2,
            "rounding_10m": {"T20": {"median_rounding_error_share": 0.1, "position_months_over_50pct": 1, "positions": 9}},
            "T20_mean_net_weight_by_sector": {"energy": 0.1}, "T21_mean_net_weight_by_sector": {"energy": 0.1}}
    (out / "diagnostics.json").write_text(json.dumps(diag))
    (out / "build0.json").write_text(json.dumps({"A4": {"corr": 0.5}}))
    pd.DataFrame([{"series": "v1.1|decisive", "period": "2020-01..2026-09", "sharpe": 0.9, "ann_return_%": 5,
                   "ann_vol_%": 6, "max_drawdown_%": -15, "ES97.5_monthly_%": 6, "turnover_x_pa": 3}]).to_csv(
        out / "performance.csv", index=False)
    monkeypatch.setattr(R, "OUT", out)
    monkeypatch.setattr(R, "REPORT", tmp_path / "r.md")
    R.write()
    text = (tmp_path / "r.md").read_text()
    assert "A4 and Amendment 4" in text and "| T20 commodity carry |" in text
