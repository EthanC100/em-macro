"""T23-T24 window helper: moves only the schedule start and contract loading, and restores them (synthetic)."""
import pandas as pd

from em_macro import commod_data as CD
from em_macro import t2324_window as WIN


def test_apply_and_restore_change_only_the_window():
    before = (CD.ASSEMBLY_START, CD.MarketData.__init__.__defaults__, CD.BUFFER_DAYS, CD.LAST_DAYS_GUARD,
              CD.F13_TARGET_DAYS, CD.F13_WINDOW_DAYS, CD.COVERAGE_START, CD.DESIGN_START)
    assert before[0] == pd.Timestamp("1990-01-01") and before[1] == (None, "1985-01-01")
    WIN.apply()
    try:
        assert CD.ASSEMBLY_START == pd.Timestamp("1977-01-01")
        assert CD.MarketData.__init__.__defaults__ == (None, "1970-01-01")
        # roll rule, F13 window, coverage and design constants untouched
        assert (CD.BUFFER_DAYS, CD.LAST_DAYS_GUARD, CD.F13_TARGET_DAYS, CD.F13_WINDOW_DAYS,
                CD.COVERAGE_START, CD.DESIGN_START) == before[2:]
    finally:
        WIN.restore()
    assert (CD.ASSEMBLY_START, CD.MarketData.__init__.__defaults__) == before[:2]


def test_phase1_counts_cover_1978_to_1999():
    from em_macro.config import RESULTS
    c = pd.read_csv(RESULTS / "T23-T24" / "availability_counts.csv", index_col=0)
    assert c.index[0] == "1978-01" and c.index[-1] == "1999-12" and len(c) == 264
    t21, t22 = c["T21_active_markets"], c["T22_active_instruments"]
    assert t21[t21 >= 6].index[0] == "1979-05" and t22[t22 >= 6].index[0] == "1979-04"
    assert (t21.loc["1979-05":] >= 6).all() and (t22.loc["1979-04":] >= 6).all()
