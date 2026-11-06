"""Synthetic tests for the T23-T24 runner (em_macro/t2324.py).  No real data: fabricated monthly series and the toy
contracts of test_t2022."""
import numpy as np
import pandas as pd
import pytest

from em_macro import commod_data as CD
from em_macro import t2022
from em_macro import t2324 as R
from test_t2022 import _toy_market

IDX = pd.period_range("1979-01", "2000-01", freq="M")


def with_t(t: float, seed: int, sub_a_shift: float = 0.0, w=R.W23) -> pd.Series:
    """Monthly series on IDX whose Newey-West (6) t over window `w` is exactly `t` (t is linear in the mean)."""
    e = pd.Series(np.random.default_rng(seed).normal(0, 0.02, len(IDX)), index=IDX)
    e = e - R.win(e, w).mean()
    _, t1 = t2022.nw_tstat(R.win(e + 0.001, w), 6)
    se = 0.001 / t1
    x = e + t * se
    if sub_a_shift:
        x.loc[:R.SUB_A_END] += sub_a_shift
        x.loc[R.SUB_B[0]:] -= sub_a_shift * len(R.win(x, (R.W23[0], R.SUB_A_END))) / len(R.win(x, R.SUB_B))
    return x


def pack(net: pd.Series, cost=0.001) -> dict:
    c = pd.Series(cost, index=net.index)
    return {"net": net, "gross": net + 2 * c, "cost1": c}


def held20(first="1981-05"):
    h = pd.DataFrame({"X": 0.0}, index=IDX)
    h.loc[first:, "X"] = 1.0
    return h


def control():
    return {"net": pd.Series(np.random.default_rng(9).normal(0, 0.02, len(IDX)), index=IDX)}


def g(out, trial, k):
    return next(x for x in out[trial] if x["#"] == k)


@pytest.mark.parametrize("t23,t24,s1", [(2.5, 1.0, True),     # T23 smaller p: needs p < 0.0114 (t > 2.28): 2.5 passes
                                        (2.1, 1.0, False),    # t > 2 but Holm-adjusted p = 2 x 0.018 > 0.0228
                                        (2.1, 3.0, True),     # T24 smaller p and < 0.0114: T23 needs only t > 2
                                        (2.2, 2.1, False),    # T24 smaller p but >= 0.0114: T23 fails
                                        (1.9, 4.0, False)])   # t < 2 fails regardless
def test_t23_s1_holm_boundaries(t23, t24, s1):
    out = R.evaluate(pack(with_t(t23, 1)), pack(with_t(t24, 2, w=R.W24)), control(), held20())
    st = out["_stats"]
    assert st["T23_nw"]["t"] == pytest.approx(t23, rel=1e-6) and st["T24_nw"]["t"] == pytest.approx(t24, rel=1e-6)
    assert st["p_holm"] == pytest.approx(t2022.holm(st["p_raw"]))
    assert g(out, "T23", "S1")["pass"] is s1


def test_t24_s1_is_the_sharpe_floor_and_its_p_does_not_gate():
    out = R.evaluate(pack(with_t(1.0, 1)), pack(with_t(1.5, 2)), control(), held20())
    sr = t2022.sr(R.win(with_t(1.5, 2), R.W24))
    assert g(out, "T24", "S1")["pass"] is (sr > 0.20)
    assert out["_stats"]["p_holm"]["T24"] > R.S1_P            # would fail a significance gate, which T24 does not have
    assert [x["#"] for x in out["T24"]] == ["S1", "S3", "A"]


def test_gate_a_uses_only_the_never_computed_months():
    x = with_t(3.0, 1, sub_a_shift=-0.03)                        # sub-window (a) negative, whole window strongly positive
    assert R.win(x, R.W23).mean() > 0 and R.win(x, (R.W23[0], R.SUB_A_END)).mean() < 0
    out = R.evaluate(pack(x), pack(x), control(), held20())
    assert not g(out, "T23", "A")["pass"] and not g(out, "T24", "A")["pass"]
    assert not out["T23_overall_pass"] and not out["T24_overall_pass"]
    assert "141 months" in g(out, "T23", "A")["value"] and "141 months" in g(out, "T24", "A")["value"]


def test_s2_regression_span_starts_at_the_controls_first_held_month():
    out = R.evaluate(pack(with_t(2.5, 1)), pack(with_t(1.0, 2)), control(), held20("1981-05"))
    al = out["_stats"]["alpha_vs_T20"]
    assert al["span"] == ["1981-05", "1999-12"] and al["months"] == len(pd.period_range("1981-05", "1999-12", freq="M"))
    ref = t2022.nw_regression(R.win(with_t(2.5, 1), ("1981-05", "1999-12")), R.win(control()["net"], ("1981-05", "1999-12")))
    assert al["alpha_t"] == pytest.approx(ref["alpha_t"])


def test_breakeven_and_s3():
    x = pd.Series(0.004, index=IDX) + pd.Series(np.random.default_rng(3).normal(0, 0.01, len(IDX)), index=IDX)
    p = pack(x, cost=0.001)
    w = R.win(p["gross"], R.W23)
    assert R.breakeven(w, R.win(p["cost1"], R.W23)) == pytest.approx(w.mean() / 0.001)
    out = R.evaluate(p, p, control(), held20())
    assert g(out, "T23", "S3")["pass"] == bool(w.mean() / 0.001 >= 2)


def test_sleeve_positions_start_flat_at_the_window(tmp_path, monkeypatch):
    codes = ["CL", "HO", "RB", "NG", "SB", "GF", "HE"]
    for k, c in enumerate(codes):
        _toy_market(tmp_path / "norgate" / CD.SNAPSHOT / "contracts" / c, c, k)
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path))
    mks = {c: t2022.Mkt(c, pd.DataFrame(columns=["EUR", "GBP"])) for c in codes}
    sig = {c: t2022.signal_t22(mks[c], mks[c].sigma_mop()) for c in codes}
    sgm = {c: mks[c].sigma_mop() for c in codes}
    w = (pd.Period("2019-06", "M"), pd.Period("2021-12", "M"))
    sl, SG = R.make_sleeve("t", mks, sig, sgm, "T22", w)
    assert sl.held.index[0] == w[0] and sl.held.index[-1] == w[1]
    assert (sl.held.abs().sum(axis=1) > 0).any()
    d = sl.daily_gross
    assert (d[d.index < mks["CL"].rolls.at[w[0], "execution"]] == 0).all()     # nothing before the window
    # T22 half universes: months with fewer than min_active instruments hold nothing
    sl2, _ = R.make_sleeve("t", mks, sig, sgm, "T22", w, min_active=len(codes) + 1)
    assert (sl2.held == 0).all().all()
    # the same machinery without the minimum is t2022's own sleeve
    W, SG2 = t2022.build_targets(mks, sig, sgm, "T22", pd.period_range(*w, freq="M"))
    assert np.allclose(t2022.Sleeve("x", mks, W, SG2).held.values, sl.held.values)


def test_unit_break_classifier():
    d = pd.bdate_range("1985-01-01", periods=6)
    r = pd.DataFrame({"r": [0.0, 99.0, 0.0, -0.5, 0.0, 0.0], "contract": "X"}, index=d)   # x100 rescale; -50% move
    out = R.unit_break_candidates(r, d[0], d[-1])
    assert [(o["date"], o["unit_break"]) for o in out] == [(str(d[1].date()), True), (str(d[3].date()), False)]


def test_d0_hashes_match_a160bfd():
    assert R.d0_hashes()["pass"]


def test_runner_reuses_t2022_unchanged():
    for name in ("Mkt", "signal_t21", "signal_t22", "signal_t20", "build_targets", "Sleeve", "nw_tstat",
                 "nw_regression", "holm", "sr", "stats", "cap_risk", "scale_to_target"):
        assert not hasattr(R, name), name                     # nothing reimplemented in the runner
    assert R.T is t2022


def test_context_and_report_on_synthetic_sleeves(tmp_path, monkeypatch):
    import json
    codes = ["CL", "HO", "RB", "NG", "SB", "GF", "HE"]
    for k, c in enumerate(codes):
        _toy_market(tmp_path / "norgate" / CD.SNAPSHOT / "contracts" / c, c, k)
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path))
    monkeypatch.setattr(R, "W23", (pd.Period("2018-06", "M"), pd.Period("2021-12", "M")))
    monkeypatch.setattr(R, "W24", (pd.Period("2018-05", "M"), pd.Period("2021-12", "M")))
    monkeypatch.setattr(R, "SUB_A_END", pd.Period("2019-12", "M"))
    monkeypatch.setattr(R, "SUB_B", (pd.Period("2020-01", "M"), pd.Period("2021-12", "M")))
    mks = {c: t2022.Mkt(c, pd.DataFrame(columns=["EUR", "GBP"])) for c in codes}
    blend = {c: mks[c].sigma_blend() for c in codes}
    mop = {c: mks[c].sigma_mop() for c in codes}
    s21 = {c: t2022.signal_t21(mks[c]) for c in codes}
    s22 = {c: t2022.signal_t22(mks[c], mop[c]) for c in codes}
    s20 = {c: t2022.signal_t20(mks[c], "A") for c in codes}
    sl, sg = {}, {}
    for key, sig, sgm, kind, w in (("T21 sleeve|full", s21, blend, "T21", R.W23), ("T22 sleeve|full", s22, mop, "T22", R.W24),
                                   ("T20 control|full", s20, blend, "T20", R.W23)):
        sl[key], sg[key] = R.make_sleeve(key, mks, sig, sgm, kind, w)
    ser = {k: R.series(s) for k, s in sl.items()}
    crit = R.evaluate({k: ser["T21 sleeve|full"][k] for k in ("net", "gross", "cost1")},
                      {k: ser["T22 sleeve|full"][k] for k in ("net", "gross", "cost1")},
                      {"net": ser["T20 control|full"]["net"]}, sl["T20 control|full"].held)
    crit["_universe"] = {"T23": codes, "T24": codes, "T20 control": codes, "dropped_D2": []}
    start20 = R.first_held_month(sl["T20 control|full"].held, R.W23)
    ctx = R.context(sl, ser, sg, mks, start20)
    assert ctx["performance"] and "HE" in ctx["curve_moves"] and set(ctx["sub_b_vs_a160bfd_run"]) == {"T21 sleeve|full", "T22 sleeve|full"}
    out = tmp_path / "out"
    out.mkdir()
    (out / "criteria.json").write_text(json.dumps(crit, default=float))
    (out / "context.json").write_text(json.dumps(ctx, default=float))
    d2 = {"markets": {"CL": {"issues_in_window": 1, "spikes_genuine": 1, "unit_breaks": 0,
                             "large_moves": {"F1": [{"date": "2020-04-21", "contract": "CL-2020M", "unit_break": False}]}}},
          "dropped": [], "pass_no_drop": True}
    checks = {"D0": {"pass": True}, "D1": {"pass": True, "rows": 264}, "D2": d2,
              "D3": {"corr": 0.95, "months": 200, "first": "1979-04", "last": "1999-12", "markets_per_month_min": 6,
                     "markets_per_month_max": 22, "corr_to_1990_01": 0.9, "corr_1990_02_on": 0.97, "pass": True},
              "active_T21 sleeve|full": {"min_in_window": 6, "before_window": 5},
              "active_T22 sleeve|full": {"min_in_window": 6, "before_window": 5}}
    (out / "RUN.json").write_text(json.dumps({"run_started_utc": "a", "run_finished_utc": "b", "git_head_at_run": "abcdef0",
                                              "pandas": "3", "numpy": "2", "checks": checks, "readings": ["r1"]}))
    monkeypatch.setattr(R, "OUT", out)
    monkeypatch.setattr(R, "REPORT", tmp_path / "r.md")
    R.write_report()
    text = (tmp_path / "r.md").read_text()
    assert "| T23 basis-momentum (T21 rules) |" in text and "## 2. Holm adjustment" in text and "CL 2020-04-21" in text


def test_window_check_uses_targets_only(tmp_path, monkeypatch):
    codes = ["CL", "HO", "RB", "NG", "SB", "GF", "HE"]
    for k, c in enumerate(codes):
        _toy_market(tmp_path / "norgate" / CD.SNAPSHOT / "contracts" / c, c, k)
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path))
    mks = {c: t2022.Mkt(c, pd.DataFrame(columns=["EUR", "GBP"])) for c in codes}
    blend = {c: mks[c].sigma_blend() for c in codes}
    mop = {c: mks[c].sigma_mop() for c in codes}
    sig = {"T21": {c: t2022.signal_t21(mks[c]) for c in codes}, "T22": {c: t2022.signal_t22(mks[c], mop[c]) for c in codes}}
    built = []
    monkeypatch.setattr(t2022.Sleeve, "__init__", lambda self, *a, **k: built.append(1))
    # a window whose month before already has 7 active instruments must fail; nothing is built as a Sleeve
    monkeypatch.setattr(R, "W23", (pd.Period("2019-06", "M"), pd.Period("2021-12", "M")))
    monkeypatch.setattr(R, "W24", (pd.Period("2019-06", "M"), pd.Period("2021-12", "M")))
    out = R.window_check(mks, sig, {"blend": blend, "mop": mop}, codes, codes)
    assert not built
    assert out["active_T22 sleeve|full"]["before_window"] == 7 and not out["active_T22 sleeve|full"]["pass"]
    assert out["active_T22 sleeve|full"]["min_in_window"] == 7


def test_windows_after_amendment_2():
    assert R.W23 == R.W24 == (pd.Period("1979-05", "M"), pd.Period("1999-12", "M"))
    assert len(pd.period_range(R.W24[0], R.SUB_A_END, freq="M")) == 141
