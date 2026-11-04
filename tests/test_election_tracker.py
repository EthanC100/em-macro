"""Tests for the election tracker: surprise calculation, Kelly sizing, stop, poll average."""
import math

import pandas as pd
import pytest

from em_macro.election_tracker import rule as R
from em_macro.election_tracker.polls import final_poll_average


# ------------------------------------------------------------------ frozen fit
def test_frozen_fit_matches_study():
    fit = R.load_frozen_fit()
    assert fit.n == 26
    assert fit.const == pytest.approx(0.036788, abs=1e-6)
    assert fit.slope == pytest.approx(0.059550, abs=1e-6)
    assert fit.p == pytest.approx(0.2007, abs=1e-4)


# ------------------------------------------------------------------ surprise
def test_surprise_market_preferred_leader_beats_polls():
    # a leads polls by 4pp, wins by 7pp, a is market-preferred -> +3
    assert R.surprise(7.0, 4.0, +1) == pytest.approx(3.0)


def test_surprise_market_preferred_runner_up():
    # Brazil 2022 run-off as coded in the study: poll margin Lula (a) +4.0, actual +1.8,
    # Bolsonaro (b) market-preferred -> +2.2
    assert R.surprise(1.8, 4.0, -1) == pytest.approx(2.2)


def test_surprise_reproduces_study_rows():
    ev = pd.read_csv("data/events/elections.csv")
    m = pd.read_csv("results/test/event_moves.csv")
    m = m[(m.event_type == "election") & (m.asset == "FX")].dropna(subset=["surprise_mp_pp"])
    assert len(m) >= 9
    for row in m.itertuples():
        e = ev[(ev.vote_date == row.event_date[:10]) & (ev.poll_margin_pp == row.poll_margin_pp)].iloc[0]
        s = R.surprise(e.actual_margin_pp, e.poll_margin_pp, R.market_sign_from_code(e.market_preferred))
        assert s == pytest.approx(row.surprise_mp_pp, abs=1e-9)


def test_surprise_ambiguous_sign_is_excluded():
    assert R.surprise(5.0, 1.0, None) is None
    assert R.surprise(5.0, 1.0, 0) is None
    assert R.market_sign_from_code("") is None
    assert R.market_sign_from_code("ambiguous") is None
    assert R.market_sign_from_code(" A ") == 1
    assert R.market_sign_from_code("b") == -1


def test_surprise_rejects_missing_margins():
    with pytest.raises(ValueError):
        R.surprise(float("nan"), 2.0, 1)


def test_margin():
    assert R.margin(52.5, 47.5) == pytest.approx(5.0)


def test_expected_day1_move_and_oos_predictions():
    fit = R.load_frozen_fit()
    assert R.expected_day1_move(0.0, fit) == pytest.approx(fit.const)
    assert R.expected_day1_move(10.0, fit) == pytest.approx(0.0368 + 0.5955, abs=1e-3)
    # reproduce the published out-of-sample day-1 result: corr 0.72, 8 of 9 right sign
    m = pd.read_csv("results/test/event_moves.csv")
    m = m[(m.event_type == "election") & (m.asset == "FX")].dropna(subset=["surprise_mp_pp", "ab_1"])
    pred = m.surprise_mp_pp.map(lambda s: R.expected_day1_move(s, fit))
    assert len(m) == 9
    assert pred.corr(m.ab_1) == pytest.approx(0.7222, abs=1e-3)
    assert int(((pred > 0) == (m.ab_1 > 0)).sum()) == 8


# ------------------------------------------------------------------ Kelly sizing
def test_beta_posterior_mean_is_beta_9_2():
    assert R.beta_posterior_mean() == pytest.approx(9 / 11)


def test_kelly_fraction_values():
    assert R.kelly_fraction(0.6, 1.0) == pytest.approx(0.2)
    assert R.kelly_fraction(0.5, 2.0) == pytest.approx(0.25)
    assert R.kelly_fraction(0.4, 1.0) == 0.0            # negative edge -> no bet
    assert R.kelly_fraction(9 / 11, 1.0) == pytest.approx(7 / 11)


def test_kelly_fraction_rejects_bad_inputs():
    with pytest.raises(ValueError):
        R.kelly_fraction(1.2, 1.0)
    with pytest.raises(ValueError):
        R.kelly_fraction(0.6, 0.0)


def test_risk_fraction_is_capped_at_2pct():
    # half of quarter-Kelly at p = 9/11, b = 1: 0.125 * 0.636 = 7.95% -> capped at 2%
    assert R.risk_fraction(9 / 11, 1.0) == pytest.approx(0.02)


def test_risk_fraction_below_cap():
    # p = 0.55, b = 1: Kelly 0.10 -> 0.125 * 0.10 = 1.25% < 2%
    assert R.risk_fraction(0.55, 1.0) == pytest.approx(0.0125)
    assert R.risk_fraction(0.40, 1.0) == 0.0


def test_cap_binds_for_any_payoff_above_threshold():
    # cap binds when 0.125 * (p - q/b) >= 0.02, i.e. b >= q / (p - 0.16)
    p = 9 / 11
    b_star = (1 - p) / (p - 0.16)
    assert R.risk_fraction(p, b_star * 1.01) == pytest.approx(0.02)
    assert R.risk_fraction(p, b_star * 0.9) < 0.02


def test_stop_distance():
    assert R.stop_distance(1.0) == pytest.approx(1.5 * math.sqrt(5))
    with pytest.raises(ValueError):
        R.stop_distance(0.0)


def test_implied_position_long_and_short():
    pos = R.implied_position(3.0, sigma_daily_pct=0.8)
    assert pos.direction == 1
    assert pos.risk_frac == pytest.approx(0.02)
    stop = 1.5 * 0.8 * math.sqrt(5)
    assert pos.stop_pct == pytest.approx(stop)
    assert pos.notional_frac == pytest.approx(0.02 / (stop / 100))
    assert R.implied_position(-0.5, 0.8).direction == -1


def test_implied_position_no_trade():
    assert R.implied_position(None, 0.8).direction == 0
    assert R.implied_position(0.0, 0.8).notional_frac == 0.0


def test_ewma_vol_constant_series():
    assert R.ewma_vol([1.0, -1.0] * 50) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        R.ewma_vol([1.0] * 5)


# ------------------------------------------------------------------ poll average
def _polls(rows):
    return pd.DataFrame(rows, columns=["pollster", "fieldwork_end", "A", "B", "C"])


def test_poll_average_7_day_window_last_poll_per_pollster():
    vote = "2027-06-06"
    df = _polls([
        ["P1", "2027-05-20", 40, 30, 10],   # superseded by P1's later poll
        ["P1", "2027-06-01", 42, 30, 10],
        ["P2", "2027-06-02", 38, 32, 10],
        ["P3", "2027-05-10", 50, 20, 10],   # outside 7 days
    ])
    out = final_poll_average(df, vote, ["A", "B", "C"], "party")
    assert out["window_days"] == 7
    assert out["pollsters"] == ["P1", "P2"]
    assert out["a"] == "A" and out["b"] == "B"
    assert out["share_a"] == pytest.approx(40.0)
    assert out["margin"] == pytest.approx(9.0)


def test_poll_average_widens_to_10_then_21_days():
    vote = "2027-06-06"
    df = _polls([["P1", "2027-06-03", 40, 30, 10], ["P2", "2027-05-28", 44, 30, 10]])
    out = final_poll_average(df, vote, ["A", "B", "C"], "party")
    assert out["window_days"] == 10 and out["n_pollsters"] == 2
    df = _polls([["P1", "2027-06-03", 40, 30, 10], ["P2", "2027-05-20", 44, 30, 10]])
    out = final_poll_average(df, vote, ["A", "B", "C"], "party")
    assert out["window_days"] == 21 and out["n_pollsters"] == 2


def test_poll_average_excludes_vote_day_partisan_and_late_publication():
    vote = "2027-06-06"
    df = _polls([["P1", "2027-06-03", 40, 30, 10], ["P2", "2027-06-04", 44, 30, 10],
                 ["P3", "2027-06-06", 10, 80, 10], ["P4", "2027-06-04", 10, 80, 10]])
    df["partisan"] = [False, False, False, True]
    df["published"] = ["2027-06-04", "2027-06-05", None, None]
    out = final_poll_average(df, vote, ["A", "B", "C"], "party")
    assert out["pollsters"] == ["P1", "P2"]
    df.loc[1, "published"] = "2027-06-07"           # published after the vote: dropped
    out = final_poll_average(df, vote, ["A", "B", "C"], "party")
    assert out["pollsters"] == ["P1"] and out["thin"]


def test_poll_average_normalisations():
    vote = "2027-06-06"
    df = _polls([["P1", "2027-06-03", 40, 40, 20], ["P2", "2027-06-04", 45, 35, 0]])
    cand = final_poll_average(df, vote, ["A", "B", "C"], "candidate")
    assert cand["share_a"] == pytest.approx((40 + 45 / 0.8) / 2)    # P2 candidates sum to 80
    two = final_poll_average(df, vote, ["A", "B"], "two_option")
    assert two["share_a"] == pytest.approx((50 + 56.25) / 2)
    df["undecided"] = [20, 10]
    party = final_poll_average(df, vote, ["A", "B", "C"], "party")
    assert party["share_a"] == pytest.approx((40 / 0.8 + 45 / 0.9) / 2)


def test_poll_average_empty():
    out = final_poll_average(_polls([]), "2027-06-06", ["A", "B", "C"], "party")
    assert out["margin"] is None and out["n_pollsters"] == 0


# ------------------------------------------------------------------ validation against the study
def test_poll_rule_reproduces_study_poland_2023():
    """Polls parsed from the last Wikipedia revision before the 15 Oct 2023 vote (rev 1180142234).
    The study's row: PiS 34.31 vs KO 27.71, margin 6.6, last poll of each of 13 pollsters ending 8-14 Oct."""
    df = pd.read_csv("tests/fixtures/pl2023_final_polls.csv")
    out = final_poll_average(df, "2023-10-15", ["PiS", "KO", "Lewica", "Konf"], "party")
    ev = pd.read_csv("data/events/elections.csv")
    study = ev[(ev.iso3 == "POL") & (ev.vote_date == "2023-10-15") & ev.poll_margin_pp.notna()].iloc[0]
    assert out["window_days"] == 7 and out["n_pollsters"] == 13
    assert out["share_a"] == pytest.approx(study.poll_a_pct, abs=0.01)
    assert out["share_b"] == pytest.approx(study.poll_b_pct, abs=0.01)
    assert out["margin"] == pytest.approx(study.poll_margin_pp, abs=0.01)
