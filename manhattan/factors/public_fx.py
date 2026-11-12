"""Emerging-market currency deposits from the repository's public daily panel, point in time, to a cut-off.

``data/processed/daily_panel.csv`` holds spot rates (local currency per US dollar; FRED H.10 and Yahoo), policy
rates (BIS) and the US federal funds rate for six currencies from January 2005. All of it is public.

**Nothing after the cut-off is read.** ``read_panel`` reads the file line by line and stops at the first row
dated after ``end``; later rows are never parsed. The default cut-off is the exploration cap, 2019-12-31, and
the engine then reads the store through ``manhattan.roles.check_read``, which refuses anything later.

**Availability.** Every series is stamped as available one calendar day after the day it describes: the H.10
noon fixings and the policy rates are published the next business day. A decision at a day's close therefore
does not see that day's own fixing.

**The instrument.** For each currency, a deposit in that currency held by a US-dollar investor:

    V_k = V_{k−1} · ( S_{k−1} / S_k ) · ( 1 + i_{k−1} · days / 365 )

``S`` is local currency per dollar, ``i`` the local policy rate in force at the previous observation, ``days``
the calendar days between the two observations. The engine finances it at the federal funds rate
(``Instrument(kind="cash", rate="us_ff")``), so its net return is the carry trade's excess return over dollar
cash: what ``em_macro.carry`` computes month by month.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import numpy as np

from manhattan.engine.backtest import Instrument
from manhattan.engine.pit import PitStore

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data/processed/daily_panel.csv"
CURRENCIES = ("BR", "MX", "ZA", "TR", "ID", "PL")
CUTOFF = date(2019, 12, 31)
LAG_DAYS = 1
DOMAIN = "fx_daily"


def read_panel(path: Path = PANEL, end: date = CUTOFF, columns=None) -> tuple[np.ndarray, dict]:
    """(days, {column: values}) of the panel's rows dated on or before ``end``. The file is read from the top
    and reading stops at the first later row."""
    days, rows = [], []
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        keep = [i for i, h in enumerate(header) if i and (columns is None or h in columns)]
        for row in reader:
            d = date.fromisoformat(row[0])
            if d > end:
                break                                             # sorted by date: nothing below is read
            days.append(d)
            rows.append([float(row[i]) if row[i] != "" else np.nan for i in keep])
    if days != sorted(days):
        raise ValueError("the panel is not sorted by date, so stopping at the cut-off would not be safe")
    table = np.array(rows, dtype=float).reshape(len(days), len(keep))
    return np.array(days, dtype="datetime64[D]"), {header[i]: table[:, j] for j, i in enumerate(keep)}


def deposit_index(days: np.ndarray, spot: np.ndarray, rate_pct: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(days, value) of the local-currency deposit in dollars, on the days the spot rate exists; 1 on the first."""
    have = np.isfinite(spot)
    d, s = days[have], spot[have]
    filled = rate_pct.copy()
    last = np.nan
    for k in range(filled.size):                                  # the rate in force: the last one published
        last = filled[k] if np.isfinite(filled[k]) else last
        filled[k] = last
    i = filled[have] / 100.0
    start = int(np.argmax(np.isfinite(i)))                        # a deposit needs a rate
    d, s, i = d[start:], s[start:], i[start:]
    gap = np.diff(d).astype(float)
    growth = s[:-1] / s[1:] * (1.0 + i[:-1] * gap / 365.0)
    return d, np.concatenate([[1.0], np.cumprod(growth)])


def store(path: Path = PANEL, end: date = CUTOFF, currencies=CURRENCIES, lag_days: int = LAG_DAYS) -> PitStore:
    """The point-in-time store: ``fx_<c>``, ``pol_<c>``, ``dep_<c>`` for each currency and ``us_ff`` (a decimal)."""
    cols = [f"FX_{c}" for c in currencies] + [f"POL_{c}" for c in currencies] + ["US_FF"]
    days, data = read_panel(path, end, set(cols))
    out = PitStore()
    ff = data["US_FF"]
    out.add("us_ff", days, ff / 100.0, lag_days=lag_days)
    for c in currencies:
        out.add(f"fx_{c}", days, data[f"FX_{c}"], lag_days=lag_days)
        out.add(f"pol_{c}", days, data[f"POL_{c}"] / 100.0, lag_days=lag_days)
        d, v = deposit_index(days, data[f"FX_{c}"], data[f"POL_{c}"])
        out.add(f"dep_{c}", d, v, lag_days=lag_days)
    return out


def instruments(currencies=CURRENCIES, cost: float = 0.0) -> tuple:
    return tuple(Instrument(c, f"dep_{c}", kind="cash", rate="us_ff", cost=cost) for c in currencies)


def monthly(dates: np.ndarray, net: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compound daily net returns into calendar months: (months, returns)."""
    m = dates.astype("datetime64[M]")
    months = np.unique(m)
    return months, np.array([np.prod(1.0 + net[m == x]) - 1.0 for x in months])
