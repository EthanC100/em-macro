"""Tests for the T02 data-feasibility helpers (coverage summaries only; no network)."""
import pandas as pd

from em_macro import t02_data as T


def _rev_frame(editions, last_obs):
    rows = []
    for e, lo in zip(editions, last_obs):
        for p in pd.period_range("2000-01", lo, freq="M"):
            rows.append({"UNIT_MEASURE": "IX", "ACTIVITY": "BTE", "EDITION": e, "TIME_PERIOD": str(p), "OBS_VALUE": 100.0})
    return pd.DataFrame(rows)


def test_oecd_revisions_coverage_lags(tmp_path, monkeypatch):
    d = tmp_path / "oecd_stes_revisions"
    d.mkdir()
    # three editions: Jan 2020 with data to Nov 2019 (lag 2), Feb 2020 to Dec 2019 (lag 2), Dec 2020 stale (lag 12)
    df = _rev_frame(["202001", "202002", "202012"], ["2019-11", "2019-12", "2019-12"])
    df.to_csv(d / "GBR_M_PRVM_all_editions.csv", index=False)
    monkeypatch.setattr(T, "OUT", tmp_path)
    monkeypatch.setattr(T, "RAW", tmp_path / "x" / "y")
    cov = T.coverage_oecd_revisions()
    r = cov.iloc[0]
    assert r.area == "GBR" and r.measure == "PRVM"
    assert r.n_editions == 3 and r.first_edition == "202001" and r.last_edition == "202012"
    assert r.last_current_edition == "202002"
    assert r.pub_lag_months_median == 2.0 and r.n_editions_stale_gt6m == 1
    assert r.last_obs_latest_edition == "2019-12"


def test_activity_map_matches_measures():
    assert set(T.ACTIVITY) == set(T.MEASURES)
