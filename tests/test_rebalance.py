from datetime import date

import pandas as pd

from em_macro import rebalance as R


def test_scheduled_date_is_third_of_next_month():
    assert R.scheduled_date("2026-10") == date(2026, 11, 3)
    assert R.scheduled_date("2026-12") == date(2027, 1, 3)


def _positions(path):
    pd.DataFrame({"as_of": ["2026-10", "2026-10"], "effective_from": ["2026-11", "2026-11"],
                  "instrument": ["BRL", "MX10Y"], "size_pct_of_capital": ["34.810", "125.850"]}).to_csv(path, index=False)


def test_record_stamps_positions_and_logs_lateness(tmp_path, capsys):
    _positions(tmp_path / "positions.csv")
    row = R.record(today=date(2026, 11, 4), out=tmp_path)
    assert row["scheduled_date"] == "2026-11-03" and row["days_late"] == 1 and row["status"] == "LATE by 1 day"
    assert "LATE by 1 day" in capsys.readouterr().out
    pos = pd.read_csv(tmp_path / "positions.csv", dtype=str)
    assert set(pos["scheduled_date"]) == {"2026-11-03"} and set(pos["run_date"]) == {"2026-11-04"}
    assert list(pos["size_pct_of_capital"]) == ["34.810", "125.850"]     # values written back verbatim
    log = pd.read_csv(tmp_path / "rebalance_log.csv", dtype=str)
    assert list(log.columns) == R.LOG_COLUMNS and len(log) == 1 and log["n_positions"][0] == "2"


def test_record_replaces_same_month_and_keeps_history(tmp_path):
    _positions(tmp_path / "positions.csv")
    R.record(today=date(2026, 11, 4), out=tmp_path)
    R.record(today=date(2026, 11, 5), out=tmp_path)          # re-run of the same rebalance
    pd.DataFrame({"as_of": ["2026-11"], "effective_from": ["2026-12"], "instrument": ["BRL"]}).to_csv(
        tmp_path / "positions.csv", index=False)
    R.record(today=date(2026, 12, 3), out=tmp_path)
    log = pd.read_csv(tmp_path / "rebalance_log.csv", dtype=str)
    assert list(log["as_of"]) == ["2026-10", "2026-11"]
    assert list(log["run_date"]) == ["2026-11-05", "2026-12-03"] and list(log["status"]) == ["LATE by 2 days", "on time"]
