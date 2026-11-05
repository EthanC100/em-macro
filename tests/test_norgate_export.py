"""scripts/norgate_export.py against a fake norgatedata module (NDU is not available off the server)."""
import datetime as dt
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location("norgate_export", Path(__file__).parents[1] / "scripts" / "norgate_export.py")


class FakeND:
    __version__ = "fake"

    class StockPriceAdjustmentType:
        NONE = 0

    class PaddingType:
        NONE = 0

    CONTRACTS = {"6E": ["6E-2026H", "6E-2026M", "6E-2026Z"], "LLG": ["LLG-2026H", "LLG-2026Z"]}

    def futures_market_session_symbols(self):
        return list(self.CONTRACTS)

    def futures_market_session_name(self, s):
        return s

    def futures_market_session_type(self, s):
        return "Electronic"

    def futures_market_session_contracts(self, s):
        return self.CONTRACTS[s]

    def exchange_name(self, s):
        return "X"

    def last_database_update_time(self, db):
        return "2026-11-05 08:00:00"

    def first_quoted_date(self, s):
        return dt.date(2025, 6, 1)

    def last_quoted_date(self, s):
        return dt.date(2026, 3, 13) if s.endswith("H") else dt.date(2026, 12, 14)

    def first_notice_date(self, s):
        if "LLG" in s:
            raise ValueError("no first notice date")
        return pd.Timestamp("2026-03-11")

    def point_value(self, s):
        return 125000.0

    def tick_size(self, s):
        return 5e-05

    def price_timeseries(self, s, **kw):
        idx = pd.bdate_range("2026-01-02", periods=3)
        return pd.DataFrame({"Open": np.float32(1.1), "High": np.float32(1.2), "Low": np.float32(1.0),
                             "Close": np.float32(1.15), "Volume": 5.0, "Open Interest": 7.0}, index=idx)


def test_metadata_and_financial_targets(tmp_path, monkeypatch):
    ne = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(ne)
    assert ne.TARGETS["R"] == ["LLG"] and "FGBL" in ne.TARGETS and len(ne.FINANCIAL_CODES) == 10
    monkeypatch.setattr(ne, "_nd", lambda: FakeND())
    ne.main(["metadata", "--out", str(tmp_path), "--markets", "financials"])
    meta = pd.read_csv(tmp_path / "metadata.csv")
    assert set(meta["market"]) == {"6E", "R"}
    assert meta.loc[meta.contract == "6E-2026H", "first_notice_date"].iloc[0] == "2026-03-11"
    assert meta.loc[meta.contract == "LLG-2026H", "first_notice_date"].isna().all()
    info = json.loads((tmp_path / "metadata_fields.json").read_text())
    assert info["fields"]["first_notice_date"]["errors"] == 2
    assert info["fields"]["lowest_ever_tick_size"]["available"] is False      # absent from the fake module
    cov = pd.read_csv(tmp_path / "coverage.csv")
    assert set(cov.loc[cov.status == "MISSING", "market"]) == {"6M", "6B", "6L", "6Z", "FGBL", "FOAT",
                                                                "FBTP", "FBON"}
    ne.main(["export", "--out", str(tmp_path / "x"), "--markets", "6E"])
    assert (tmp_path / "x" / "contracts" / "6E" / "6E-2026H.csv").exists()
