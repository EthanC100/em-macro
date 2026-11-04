"""Tests for the election tracker's FX windows, trade scoring, pre-registration and alert (no network)."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from em_macro.election_tracker import alert, fx, prereg
from em_macro.election_tracker import rule as R


# ------------------------------------------------------------------ study windows
def test_window_dates_sunday_vote():
    w = fx.window_dates("2027-06-06")                 # Sunday
    assert w["base"] == pd.Timestamp("2027-06-04")     # Friday
    assert w[1] == pd.Timestamp("2027-06-07")          # Monday
    assert w[5] == pd.Timestamp("2027-06-11")


def test_window_dates_weekday_vote():
    w = fx.window_dates("2028-04-12")                 # Wednesday
    assert w["base"] == pd.Timestamp("2028-04-11") and w[1] == pd.Timestamp("2028-04-13")


def test_raw_moves_match_study_definition():
    idx = pd.bdate_range("2027-05-01", "2027-06-30")
    spot = pd.Series(20.0, index=idx)
    spot.loc["2027-06-07":] = 19.0                    # local currency appreciates on day 1
    x = fx.level(spot)
    m = fx.raw_moves(x, "2027-06-06")
    assert m[1] == pytest.approx(100 * np.log(20 / 19))
    assert m[5] == pytest.approx(m[1])


def test_raw_moves_stale_end_is_nan():
    idx = pd.bdate_range("2027-05-01", "2027-06-04")  # series stops at the base date
    x = fx.level(pd.Series(20.0, index=idx))
    assert np.isnan(fx.raw_moves(x, "2027-06-06")[1])


def test_abnormal_moves_remove_factor_moves():
    idx = pd.bdate_range("2027-05-01", "2027-06-30")
    x = pd.Series(0.0, index=idx)
    x.loc["2027-06-07":] = 1.0
    fac = {"DXY": pd.Series(0.0, index=idx), "US10": pd.Series(0.0, index=idx), "VIX": pd.Series(0.0, index=idx)}
    fac["DXY"].loc["2027-06-07":] = 2.0
    betas = {"alpha_per_day": 0.0, "b_DXY": -0.5, "b_US10": 0.0, "b_VIX": 0.0}
    ab = fx.abnormal_moves(fx.raw_moves(x, "2027-06-06"), "2027-06-06", betas, fac)
    assert ab[1] == pytest.approx(1.0 - (-0.5 * 2.0))


def test_frozen_betas_only_for_study_countries():
    assert fx.frozen_betas("MX")["b_DXY"] == pytest.approx(-0.5453902726766596)
    assert fx.frozen_betas("KR") is None


# ------------------------------------------------------------------ trade
def test_entry_and_exit_dates():
    e = fx.entry_date("2027-06-06")                    # Sunday-night result
    assert e == pd.Timestamp("2027-06-07")
    assert fx.exit_date(e) == pd.Timestamp("2027-06-14")
    assert fx.entry_date("2028-04-12") == pd.Timestamp("2028-04-13")


def test_trade_return_and_close_based_stop():
    idx = pd.bdate_range("2027-06-01", "2027-06-30")
    x = pd.Series(0.0, index=idx)
    x.loc["2027-06-08":] = 0.5
    x.loc["2027-06-14":] = 1.0
    t = fx.trade_return(x, pd.Timestamp("2027-06-07"), +1, stop_pct=3.0)
    assert t["trade_return_pct"] == pytest.approx(1.0) and t["stopped"] is False
    assert t["post_move_pct"] == pytest.approx(1.0)
    t = fx.trade_return(x, pd.Timestamp("2027-06-07"), -1, stop_pct=0.4)
    assert t["trade_return_pct"] == pytest.approx(-0.5) and t["stopped"] is True
    assert t["exit"] == dt.date(2027, 6, 8)
    assert t["post_move_pct"] == pytest.approx(-1.0)          # post-day-1 move ignores the stop


def test_sigma_daily_uses_data_up_to_asof():
    idx = pd.bdate_range("2026-01-01", "2027-06-30")
    rng = np.random.default_rng(0)
    x = pd.Series(np.cumsum(rng.normal(0, 0.7, len(idx))), index=idx)
    x.loc["2027-06-01":] += np.cumsum(np.full(len(x.loc["2027-06-01":]), 5.0))
    s = fx.sigma_daily(x, "2027-05-31")
    assert 0.5 < s < 0.9


# ------------------------------------------------------------------ results parsing
RESULTS_HTML = """
<table class="wikitable"><tr><th>Party</th><th>Votes</th><th>%</th><th>Seats</th></tr>
<tr><td>National Regeneration Movement (Morena)</td><td>20,000,000</td><td>41.20</td><td>200</td></tr>
<tr><td>National Action Party (PAN)</td><td>8,500,000</td><td>17.50</td><td>80</td></tr>
<tr><td>Valid votes</td><td>48,000,000</td><td>97.0</td><td></td></tr>
</table>"""


def test_parse_results():
    out = alert.parse_results(RESULTS_HTML, {"Morena": "Morena|National Regeneration", "PAN": r"National Action|\bPAN\b"})
    assert out == {"Morena": 41.2, "PAN": 17.5}


def test_parse_results_no_table():
    assert alert.parse_results("<p>no results yet</p>", {"A": "A", "B": "B"}) == {}


# ------------------------------------------------------------------ pre-registration round trip
ROW = {"id": "xx-2027-legislative", "country": "Testland", "currency": "MXN", "date": "2027-06-06",
       "type": "legislative", "rounds": "1", "status": "scheduled", "source_url": "https://example.org"}
CFG = {"race_kind": "party", "options": {"A": "A", "B": "B"}, "market_preferred": "B",
       "market_sign_justification": "Analysts prefer B.", "market_sign_sources": ["https://example.org/note"],
       "quantity": "A-B margin.", "quantity_note": None, "tz": "America/Mexico_City"}
SNAP = {"a": "A", "b": "B", "share_a": 45.0, "share_b": 35.0, "margin": 10.0, "window_days": 7,
        "n_pollsters": 3, "revid": 123, "rev_timestamp": "2027-05-20T00:00:00Z"}


def test_prereg_render_and_parse_block():
    text = prereg.render(ROW, CFG, SNAP, dt.datetime(2027, 5, 23, 7, 0, tzinfo=dt.timezone.utc))
    assert "Market-preferred side: B" in text and "**-1**" in text
    blk = prereg.parse_block(text)
    assert blk["market_preferred"] == "B" and blk["days_before_vote"] == 14
    assert blk["current_poll_average"]["margin"] == 10.0
    assert blk["rule"]["risk_cap"] == 0.02 and blk["rule"]["hold_days"] == 5


def test_prereg_render_unclassified():
    text = prereg.render(ROW, {**CFG, "market_preferred": None}, SNAP, dt.datetime(2027, 5, 23, tzinfo=dt.timezone.utc))
    assert "NOT CLASSIFIED" in text and prereg.parse_block(text)["market_preferred"] is None


# ------------------------------------------------------------------ alert end to end (network stubbed)
@pytest.fixture
def stubbed(monkeypatch):
    cal = pd.DataFrame([ROW])
    monkeypatch.setattr(alert, "load_calendar", lambda: cal)
    monkeypatch.setattr(alert, "load_config", lambda: {ROW["id"]: {**CFG, "yahoo": "MXN=X"}})
    monkeypatch.setattr(alert.snapshots, "final", lambda eid: SNAP)
    monkeypatch.setattr(alert.prereg, "committed_block", lambda eid, cutoff: {"market_preferred": "B", "commit": "abc1234"})
    idx = pd.bdate_range("2026-01-01", "2027-06-08")
    spot = pd.Series(20 * np.exp(np.random.default_rng(1).normal(0, 0.007, len(idx)).cumsum()), index=idx)
    monkeypatch.setattr(alert.fx, "spot", lambda *a, **k: (spot, "test series"))
    monkeypatch.setattr(alert, "today", lambda: dt.date(2027, 6, 7))


def test_build_signal_market_preferred_runner_up(stubbed):
    # polls A +10; result A 44 vs B 38 (+6); B market-preferred -> surprise = (6 - 10) * -1 = +4
    sig = alert.build_signal(ROW["id"], {"A": 44.0, "B": 38.0}, "test")
    assert sig["status"] == "signal" and sig["market_sign"] == -1
    assert sig["surprise_pp"] == pytest.approx(4.0)
    fit = R.load_frozen_fit()
    assert sig["expected_day1_pct"] == pytest.approx(fit.const + 4.0 * fit.slope)
    assert sig["direction"] == 1
    # observation only: logged size 0, the rule's own size kept for scoring
    assert sig["position_label"] == "paper, observation only"
    assert sig["risk_frac"] == 0.0 and sig["notional_frac"] == 0.0
    assert sig["rule_risk_frac"] == pytest.approx(0.02)
    assert sig["rule_notional_frac"] == pytest.approx(0.02 / (sig["stop_pct"] / 100))
    assert sig["stop_pct"] == pytest.approx(1.5 * sig["sigma_daily_pct"] * np.sqrt(5))
    assert sig["entry_date"] == "2027-06-07" and sig["exit_date"] == "2027-06-14"
    title, body = alert.issue_text(sig)
    assert title == "[ELECTION] Testland 2027-06-06: surprise +4.0pp"
    assert "Paper, observation only: size 0" in body
    assert "**long MXN vs USD, size 0**" in body and "paper, observation only" in body
    assert "not established" in body


def test_build_signal_excluded_without_prereg(stubbed, monkeypatch):
    monkeypatch.setattr(alert.prereg, "committed_block", lambda eid, cutoff: None)
    sig = alert.build_signal(ROW["id"], {"A": 44.0, "B": 38.0}, "test")
    assert sig["status"].startswith("excluded") and sig["surprise_pp"] is None and sig["direction"] == 0
    assert sig["position_label"] == "paper, observation only" and sig["risk_frac"] == 0.0
    assert alert.issue_text(sig)[0].endswith("surprise n/a")


def test_signals_csv_logs_size_zero_and_scores_the_rule(stubbed, monkeypatch, tmp_path):
    data = tmp_path / "data" / "elections"
    data.mkdir(parents=True)
    monkeypatch.setattr(alert, "SIGNALS", data / "signals.csv")
    monkeypatch.setattr(alert, "DATA", data)
    sig = alert.build_signal(ROW["id"], {"A": 44.0, "B": 38.0}, "test")
    alert.append_signal(sig)
    df = pd.read_csv(data / "signals.csv")
    assert list(df.columns) == alert.SIGNAL_COLS
    assert df.loc[0, "position_label"] == "paper, observation only"
    assert df.loc[0, "risk_frac"] == 0 and df.loc[0, "notional_frac"] == 0
    assert df.loc[0, "rule_risk_frac"] == pytest.approx(0.02) and pd.isna(df.loc[0, "scored"])
    # score after the exit date: local currency up 1% from the entry close, no stop
    idx = pd.bdate_range("2026-01-01", "2027-06-30")
    spot = pd.Series(20.0, index=idx)
    spot.loc["2027-06-08":] = 20.0 * np.exp(-0.01)
    monkeypatch.setattr(alert.fx, "spot", lambda *a, **k: (spot, "test series"))
    monkeypatch.setattr(alert.fx, "factor_levels", lambda *a: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(alert.fx, "_frankfurter", lambda *a: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(alert, "today", lambda: dt.date(2027, 6, 20))
    assert alert.score() == [ROW["id"]]
    r = pd.read_csv(data / "signals.csv").iloc[0]
    assert r["post_day1_move_pct"] == pytest.approx(1.0) and r["trade_return_pct"] == pytest.approx(1.0)
    assert r["rule_pnl_nav_pct"] == pytest.approx(r["rule_notional_frac"] * 1.0)
    assert r["scored"] == "yes" and r["risk_frac"] == 0


def test_committed_block_uses_last_commit_before_vote(tmp_path):
    import os
    import subprocess

    def git(*args, date=None):
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org"}
        if date:
            env.update({"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
        subprocess.run(["git", *args], cwd=tmp_path, env=env, check=True, capture_output=True)

    git("init", "-q")
    doc = tmp_path / "docs" / "elections" / f"{ROW['id']}.md"
    doc.parent.mkdir(parents=True)
    w = dt.datetime(2027, 5, 23, tzinfo=dt.timezone.utc)
    doc.write_text(prereg.render(ROW, {**CFG, "market_preferred": None}, SNAP, w))
    git("add", "."); git("commit", "-q", "-m", "prereg", date="2027-05-23T07:00:00+00:00")
    doc.write_text(prereg.render(ROW, CFG, SNAP, w))                     # sign added before the vote
    git("commit", "-q", "-am", "sign", date="2027-06-01T07:00:00+00:00")
    doc.write_text(prereg.render(ROW, {**CFG, "market_preferred": "A"}, SNAP, w))   # changed after the vote
    git("commit", "-q", "-am", "late", date="2027-06-07T07:00:00+00:00")
    cutoff = "2027-06-06T06:00:00Z"                                      # vote day 00:00 in Mexico City
    assert prereg.committed_block(ROW["id"], cutoff, root=tmp_path)["market_preferred"] == "B"
    assert prereg.committed_block(ROW["id"], "2027-05-01T00:00:00Z", root=tmp_path) is None
