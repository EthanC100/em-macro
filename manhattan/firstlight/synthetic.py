"""First Light harness: a seeded SYNTHETIC futures-like daily dataset, its contract, and its capped load.

Nothing here reads market data. The values are drawn from ``numpy.random.default_rng(seed)``: a few excess-return
indices on weekdays from 2005-01-03 to 2019-12-31, each a random walk whose drift follows a slow AR(1) regime (so a
trend rule has something to find in some series and loses in others). The file is marked synthetic in its contract
(``synthetic: true``, ``real_data: false``, ``licensed: false``) and identified by its SHA-256 and by the
point-in-time data hash of the store it loads into.

Loading goes through ``cap.CappedStore`` only, so nothing dated or published after 2019-12-31 can enter memory.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date
from pathlib import Path

import numpy as np

from manhattan import spec as S

from . import cap

GENERATOR = "manhattan.firstlight.synthetic/1"
START, END = date(2005, 1, 3), cap.DATA_END
SERIES = ("syn_fut_a", "syn_fut_b", "syn_fut_c", "syn_fut_d")
CSV_NAME, CONTRACT_NAME = "synthetic_futures.csv", "contract.json"
LAG_DAYS = 0                      # a settlement is usable at the close of the day it describes


class DatasetError(RuntimeError):
    """The synthetic dataset or its contract does not match (fail closed)."""


def weekdays(start: date = START, end: date = END) -> np.ndarray:
    d = np.arange(np.datetime64(start.isoformat(), "D"), np.datetime64(end.isoformat(), "D") + np.timedelta64(1, "D"))
    return d[np.is_busday(d)]


def generate(seed: int) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """(days, {series: index levels}). Deterministic in ``seed``; nothing but numpy's generator is read."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise DatasetError("the seed is a nonnegative whole number")
    rng = np.random.default_rng(seed)
    days = weekdays()
    n = days.size
    out = {}
    for k, name in enumerate(SERIES):
        vol = 0.008 + 0.002 * k                                  # daily volatility, about 13% to 22% a year
        regime = np.zeros(n)
        shocks = rng.standard_normal(n)
        for t in range(1, n):                                    # slow drift regime, half-life about 120 days
            regime[t] = 0.9942 * regime[t - 1] + 0.00006 * shocks[t]
        r = regime + vol * rng.standard_normal(n)
        out[name] = np.round(100.0 * np.cumprod(1.0 + r), 8)
    return days, out


def to_csv(days: np.ndarray, levels: dict[str, np.ndarray]) -> bytes:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["date", *SERIES])
    for i, d in enumerate(days):
        w.writerow([str(d), *(repr(float(levels[s][i])) for s in SERIES)])
    return buf.getvalue().encode("utf-8")


def from_csv(raw: bytes) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
    if not rows or rows[0] != ["date", *SERIES]:
        raise DatasetError("the synthetic file does not have the expected columns")
    body = rows[1:]
    days = np.array([r[0] for r in body], dtype="datetime64[D]")
    return days, {s: np.array([float(r[i + 1]) for r in body]) for i, s in enumerate(SERIES)}


def make(seed: int) -> tuple[dict, bytes]:
    """(contract, file bytes), in memory: nothing is written (``pit_data_hash`` is filled after ``load``)."""
    days, levels = generate(seed)
    raw = to_csv(days, levels)
    contract = {"schema": "firstlight.synthetic_contract/1", "synthetic": True, "real_data": False, "licensed": False,
                "generator": GENERATOR, "seed": seed, "series": list(SERIES), "start": str(days[0]),
                "end": str(days[-1]), "rows": int(days.size), "availability_lag_days": LAG_DAYS,
                "file": CSV_NAME, "file_sha256": hashlib.sha256(raw).hexdigest(),
                "note": "SYNTHETIC: generated from a seed; no market data, no licensed source"}
    return contract, raw


def write_file(directory: Path, raw: bytes) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / CSV_NAME).write_bytes(raw)


def build(directory: Path, seed: int) -> dict:
    """Write the synthetic file under ``directory``; return its contract."""
    contract, raw = make(seed)
    write_file(directory, raw)
    return contract


def load(directory: Path, contract: dict) -> cap.CappedStore:
    """The file, checked against its contract, loaded through the cap. Returns the capped store."""
    raw = (directory / contract["file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != contract["file_sha256"]:
        raise DatasetError("the synthetic file does not match its contract's SHA-256")
    if contract.get("synthetic") is not True or contract.get("real_data") is not False:
        raise DatasetError("First Light's harness loads a dataset marked synthetic only")
    days, levels = from_csv(raw)
    capped = cap.CappedStore(synthetic=True)
    for s in SERIES:
        capped.add(s, days, levels[s], lag_days=LAG_DAYS)
    return capped


def write_contract(directory: Path, contract: dict) -> bytes:
    data = S.canonical_bytes(contract)
    (directory / CONTRACT_NAME).write_bytes(data)
    return data


def read_contract(directory: Path) -> dict:
    return json.loads((directory / CONTRACT_NAME).read_bytes().decode("utf-8"))
