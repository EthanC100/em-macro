"""Window settings for trials T23-T24 (T21 and T22 on 1980-1999; docs/prereg/T23-T24_pre2000_backtest.md).

The trial code at a160bfd (em_macro/commod_data.py, commod_build0.py, t2022.py) is used unchanged.  Its only
hard-coded dates that matter before 2000 are the start of the rebalance schedule (``commod_data.ASSEMBLY_START``,
1990-01) and the earliest contract file loaded (``MarketData(load_from="1985-01-01")``).  This module moves both
earlier, inside this process only, without editing any file: nothing about signals, roll rule, sizing, costs or
statistics is touched.
"""
from __future__ import annotations

import pandas as pd

from . import commod_data as CD

SCHEDULE_START = pd.Timestamp("1977-01-01")    # schedule from the first month with a prior settlement
LOAD_FROM = "1970-01-01"                       # every contract file is loaded
CHECK = (pd.Period("1978-01", "M"), pd.Period("1999-12", "M"))   # Phase 1 availability months
WINDOW_END = pd.Period("1999-12", "M")

_ORIG = {"ASSEMBLY_START": CD.ASSEMBLY_START, "defaults": CD.MarketData.__init__.__defaults__}


def apply() -> None:
    """Move the schedule start and the contract loading earlier (process-local; idempotent)."""
    CD.ASSEMBLY_START = SCHEDULE_START
    CD.MarketData.__init__.__defaults__ = (None, LOAD_FROM)


def restore() -> None:
    CD.ASSEMBLY_START = _ORIG["ASSEMBLY_START"]
    CD.MarketData.__init__.__defaults__ = _ORIG["defaults"]
