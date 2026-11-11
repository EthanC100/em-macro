"""D005: volatility floor for managed currencies on the v1.0 book (em_macro/d005.py).

Synthetic inputs only (no download, no live result is written); plus checks that the repository's managed list,
the workflow step, the protected paths and the Ledger read it as documented.
"""
import csv
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from em_macro import d005 as D
from em_macro import systematic as SY

ROOT = Path(__file__).resolve().parents[1]
FX = list(SY.FX_INSTR)                    # BRL MXN ZAR TRY IDR PLN GBP COP CLP EUR
BONDS = ["MX10Y", "TR10Y"]


def _hist(seed: int = 0, n: int = 36) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    vols = {k: 0.09 / np.sqrt(12) for k in FX + BONDS}
    vols["TRY"] = 0.03 / np.sqrt(12)
    return pd.DataFrame({k: rng.normal(0, v, n) for k, v in vols.items()})


def _vol(try_vol: float = 0.0385) -> pd.Series:
    v = pd.Series({"BRL": 0.106, "MXN": 0.0976, "ZAR": 0.0862, "TRY": try_vol, "IDR": 0.0655, "PLN": 0.0831,
                   "GBP": 0.0684, "COP": 0.1181, "CLP": 0.1126, "EUR": 0.0704, "MX10Y": 0.0559, "TR10Y": 0.1551})
    return v


def _w() -> pd.Series:
    w = pd.Series(0.0, index=FX + BONDS)
    w.update(pd.Series({"TRY": 0.9578, "IDR": 0.5631, "BRL": 0.3481, "MXN": -0.3778, "PLN": -0.4438, "EUR": -0.5241,
                        "MX10Y": 1.2585, "TR10Y": -0.4532}))
    return w


# ----------------------------------------------------------------------------- the override
def test_floor_is_the_median_of_the_eight_em_currencies_only():
    v = _vol()
    assert D.EM_FX == ["BRL", "MXN", "ZAR", "TRY", "IDR", "PLN", "COP", "CLP"]
    assert D.vol_floor(v) == pytest.approx(np.median(v[D.EM_FX]))
    v2 = v.copy()
    v2[["GBP", "EUR", "MX10Y"]] = 9.0                         # not emerging-market currencies: ignored
    assert D.vol_floor(v2) == D.vol_floor(v)


def test_floored_leg_gets_the_inverse_vol_weight_and_the_book_is_rescaled_to_10pct():
    w, v, h = _w(), _vol(), _hist()
    adj = D.adjust(w, v, h, ["TRY"])
    floor, scale = adj.attrs["floor"], adj.attrs["scale"]
    assert adj.at["TRY", "floored"] and adj["floored"].sum() == 1
    assert adj.at["TRY", "vol_used"] == pytest.approx(floor)
    # TRY: v1.0 weight x (own vol / floor), then the common book scale; every other leg: v1.0 weight x scale
    assert adj.at["TRY", "d005_weight"] == pytest.approx(w["TRY"] * v["TRY"] / floor * scale)
    others = w.index.drop("TRY")
    assert np.allclose(adj.loc[others, "d005_weight"], w[others] * scale)
    assert D.pro_forma_vol(adj["d005_weight"], h) == pytest.approx(0.10)
    assert (np.sign(adj["d005_weight"]) == np.sign(w)).all()   # sides never change
    assert abs(adj.at["TRY", "d005_weight"]) < abs(w["TRY"])


def test_no_change_when_the_managed_currency_is_above_the_floor_or_not_held_or_not_listed():
    w, h = _w(), _hist()
    for v, managed, ww in ((_vol(try_vol=0.20), ["TRY"], w),    # above the floor
                           (_vol(), ["COP"], w),                   # listed but not held
                           (_vol(), [], w),                        # nothing listed
                           (_vol(), ["TRY"], w.where(w.index != "TRY", 0.0))):   # TRY not held
        adj = D.adjust(ww, v, h, managed)
        assert adj.attrs["scale"] == 1.0 and not adj["floored"].any()
        assert np.allclose(adj["d005_weight"], ww)


def test_gross_leverage_cap_is_kept():
    w, v, h = _w(), _vol(), _hist() * 0.2                    # very calm history: the 10% rescale would lever up
    adj = D.adjust(w, v, h, ["TRY"], cap=6.0)
    assert adj["d005_weight"].abs().sum() == pytest.approx(6.0)
    assert D.pro_forma_vol(adj["d005_weight"], h) < 0.10


def test_bond_legs_are_never_floored():
    adj = D.adjust(_w(), _vol(), _hist(), ["TRY", "TR10Y"])
    assert adj["floored"].sum() == 1 and adj.at["TRY", "floored"]


# ----------------------------------------------------------------------------- the managed list
def test_repository_managed_list_has_try_with_its_imf_classification():
    rows = D.load_managed()
    assert [r["currency"] for r in rows] == ["TRY"]
    r = rows[0]
    assert r["imf_classification"] == "crawl-like arrangement" and r["imf_managed"]
    assert "IMF" in r["source"] and "April 30, 2026" in r["source"] and r["date"] == "2026-11-11"
    assert r["evidence"]
    with (ROOT / "config/v1_managed_fx.csv").open(newline="", encoding="utf-8") as f:
        assert csv.DictReader(f).fieldnames == D.MANAGED_COLUMNS


def test_invalid_managed_rows_are_refused(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("currency,imf_classification,source,date,evidence\n"
                 "USD,crawl-like arrangement,IMF,2026-11-11,x\n"
                 "TRY,,IMF,11 Nov 2026,x\n", encoding="utf-8")
    with pytest.raises(ValueError) as e:
        D.load_managed(p)
    msg = str(e.value)
    assert "USD" in msg and "imf_classification and source are required" in msg and "not YYYY-MM-DD" in msg


def test_a_currency_the_imf_does_not_class_as_managed_is_still_applied(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("currency,imf_classification,source,date,evidence\n"
                 "IDR,floating,IMF AREAER,2026-11-11,listed by Ethan: D005 key factors\n", encoding="utf-8")
    rows = D.load_managed(p)
    assert rows[0]["currency"] == "IDR" and not rows[0]["imf_managed"]


# ----------------------------------------------------------------------------- booking and P&L
def _state(n: int = 8):
    months = pd.period_range("2026-07", periods=n, freq="M")
    rng = np.random.default_rng(1)
    fx = pd.DataFrame(rng.normal(0, 0.02, (n, 2)), index=months, columns=["TRY", "BRL"])
    bond = pd.DataFrame(rng.normal(0, 0.01, (n, 1)), index=months, columns=["TR10Y"])
    W = pd.DataFrame({"TRY": 0.9, "BRL": 0.3, "TR10Y": -0.4}, index=months)
    inp = {"months": months, "fx": {"ret": fx}, "bond": {"ret": bond}, "cost": {"TRY": 0.003, "BRL": 0.001, "TR10Y": 0.003}}
    return {"inp": inp, "W": W}, months, fx, bond


def test_pnl_adjustment_uses_v10_timing_and_costs():
    st, months, fx, bond = _state()
    t = months[3]                                              # D005 booked at as_of t only
    log = pd.DataFrame([{"as_of": str(t), "instrument": "TRY", "book": "fx", "v10_weight": 0.9, "d005_weight": 0.4},
                        {"as_of": str(t), "instrument": "BRL", "book": "fx", "v10_weight": 0.3, "d005_weight": 0.31},
                        {"as_of": str(t), "instrument": "TR10Y", "book": "bond", "v10_weight": -0.4, "d005_weight": -0.41}])
    adj = D.pnl_adjustment(log, st)
    assert (adj[: t] == 0).all()                               # nothing before the D005 weights earn
    # t+1: FX difference earns; the trade into D005 is charged for FX
    fx_gross = -0.5 * fx.at[t + 1, "TRY"] + 0.01 * fx.at[t + 1, "BRL"]
    fx_cost = 0.5 * 0.003 + 0.01 * 0.001
    # t+2: bond difference earns (one more month's lag) and its entry is charged; FX trades back to v1.0 (charged)
    expect = -0.01 * bond.at[t + 2, "TR10Y"] - 0.01 * 0.003 - (0.5 * 0.003 + 0.01 * 0.001)
    assert adj[t + 2] == pytest.approx(expect)
    assert adj[t + 3] == pytest.approx(-0.01 * 0.003)          # bond trades back to v1.0
    assert (adj[t + 4:] == 0).all()


def test_pnl_adjustment_is_zero_without_a_booked_month():
    st, months, *_ = _state()
    assert (D.pnl_adjustment(pd.DataFrame(columns=D.WEIGHT_COLUMNS), st) == 0).all()


def test_book_paper_pnl_sets_final_net_keeps_v10_and_is_idempotent(tmp_path):
    p = tmp_path / "paper_pnl.csv"
    pd.DataFrame({"month": ["2026-11", "2026-12", "2027-01"], "net": [0.01, -0.02, 0.005],
                  "sample": ["live paper trading (after freeze)"] * 3, "model_net": [0.01, -0.02, 0.005],
                  "override_pnl": [0.0, 0.001, 0.0], "final_net": [0.01, -0.019, 0.005]}).to_csv(p, index=False)
    adj = pd.Series([0.0, 0.004, -0.001], index=pd.period_range("2026-11", periods=3, freq="M"))
    for _ in range(2):                                          # a re-run gives the same file
        out = D.book_paper_pnl(adj, p)
        assert np.allclose(out["net"], [0.01, -0.02, 0.005]) and np.allclose(out["model_net"], [0.01, -0.02, 0.005])
        assert np.allclose(out["net_before_d005"], [0.01, -0.019, 0.005])
        assert np.allclose(out["final_net"], [0.01, -0.015, 0.004])
        assert out["cumulative_final"].iloc[-1] == pytest.approx(1.01 * 0.985 * 1.004)


def test_weights_log_is_append_only_and_a_rerun_replaces_its_month(tmp_path):
    p = tmp_path / "weights.csv"
    adj = pd.DataFrame({"v10_weight": [0.9, 0.0], "d005_weight": [0.4, 0.0], "book": ["fx", "fx"]}, index=["TRY", "ZAR"])
    log = D.write_log(D.read_log(p), adj, "2026-11", p)
    log = D.write_log(D.read_log(p), adj.assign(d005_weight=[0.5, 0.0]), "2026-12", p)
    log = D.write_log(D.read_log(p), adj.assign(d005_weight=[0.6, 0.0]), "2026-12", p)
    log = D.read_log(p)
    assert list(log["as_of"]) == ["2026-11", "2026-12"]         # unheld legs are not logged
    assert list(log["d005_weight"]) == [0.4, 0.6]


def test_positions_table_reports_before_and_after():
    adj = D.adjust(_w(), _vol(), _hist(), ["TRY"])
    adj["book"] = ["fx" if k in FX else "bond" for k in adj.index]
    raw = D.positions_table(adj, "2026-11")
    assert list(raw.columns) == D.POSITION_COLUMNS
    tab = raw.set_index("instrument")
    assert set(tab.index) == {"TRY", "IDR", "BRL", "MXN", "PLN", "EUR", "MX10Y", "TR10Y"}
    assert tab.at["TRY", "effective_from"] == "2026-12" and bool(tab.at["TRY", "floored"])
    assert tab.at["TRY", "v10_size_pct_of_capital"] == pytest.approx(95.78)


# ----------------------------------------------------------------------------- wiring
def test_workflow_runs_d005_after_overlay_before_screener_and_commits_its_book():
    wf = yaml.safe_load((ROOT / ".github/workflows/systematic.yml").read_text(encoding="utf-8"))
    steps = wf["jobs"]["update"]["steps"]
    ids = [s.get("id") for s in steps]
    i = ids.index("d005")
    assert ids.index("overlay") < i < ids.index("screener") < ids.index("commit")
    assert steps[i]["run"].startswith("python -m em_macro.d005 update") and not steps[i].get("continue-on-error")
    commit = steps[ids.index("commit")]["run"]
    assert "git add -- results/systematic/d005" in commit
    assert "results/systematic/positions.csv results/systematic/paper_pnl.csv" in commit   # v1.0's files as before
    alert = next(s for s in steps if s.get("name") == "Open or update the alert issue")
    assert "d005=${{ steps.d005.outcome }}" in alert["env"]["OUTCOMES"] and "[d005]=" in alert["run"]


def test_managed_list_and_override_code_are_protected(tmp_path):
    from nightshift import protected as P
    paths = ["config/v1_managed_fx.csv", "em_macro/d005.py"]
    assert P.protected(paths) == sorted(paths)                  # CODEOWNERS block
    old = tmp_path / "CODEOWNERS"                               # e.g. dev's copy before it has merged main
    old.write_text("# protected:start\n/trials.csv @E\n# protected:end\n", encoding="utf-8")
    assert P.protected(paths + ["em_macro/overlay.py"], P.patterns(old)) == sorted(paths)
    block = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8").split("# protected:start")[1]
    assert "/config/v1_managed_fx.csv @EthanC100" in block and "/em_macro/d005.py @EthanC100" in block


def test_frozen_v10_code_is_untouched_by_d005():
    """d005.py only imports the frozen module; the monthly update's design check still passes."""
    src = (ROOT / "em_macro/d005.py").read_text(encoding="utf-8")
    assert "from . import systematic as SY" in src and "SY._check_frozen(strict=False)" in src
    SY._check_frozen(strict=False)


def test_ledger_d005_block_shows_the_unadjusted_line(tmp_path):
    from ledger import build as B
    (tmp_path / "config").mkdir()
    (tmp_path / "config/v1_managed_fx.csv").write_text((ROOT / "config/v1_managed_fx.csv").read_text(encoding="utf-8"),
                                                        encoding="utf-8")
    d = tmp_path / "results/systematic/d005"
    d.mkdir(parents=True)
    adj = D.adjust(_w(), _vol(), _hist(), ["TRY"])
    adj["book"] = ["fx" if k in FX else "bond" for k in adj.index]
    D.positions_table(adj, "2026-11").to_csv(d / "positions.csv", index=False)
    months = [{"month": "2026-11", "live": True, "net": 0.01, "net_before_d005": 0.01, "d005_adj": 0.0},
              {"month": "2026-12", "live": True, "net": 0.012, "net_before_d005": 0.02, "d005_adj": -0.008}]
    out = B.build_d005([{"as_of": "2026-11"}], months, tmp_path)
    assert out["applied"] and out["supersedes"] == "D004 rule 4" and out["managed"][0]["currency"] == "TRY"
    assert out["booked_sizes"]["TRY"] == pytest.approx(round(100 * adj.at["TRY", "d005_weight"], 3))
    assert out["comparison"][-1]["booked_index"] == pytest.approx(100 * 1.01 * 1.012, abs=1e-4)
    assert out["comparison"][-1]["unadjusted_index"] == pytest.approx(100 * 1.01 * 1.02, abs=1e-4)
    # a D005 book for another as_of is not shown as the current book
    assert B.build_d005([{"as_of": "2026-10"}], months, tmp_path)["booked_sizes"] == {}
