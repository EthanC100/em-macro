"""Shared test helpers.

Ledger tests never read the live ledger (data/ledger/decisions.csv, forecasts.csv, seals.jsonl, marks, ...): those
files grow every time a decision or forecast is logged, which broke ledger-daily on 2026-11-06 when D003 was logged
(issue #23). ``seed_ledger`` builds a ledger from the frozen seed in tests/fixtures/ledger/ (D001, D002, F001-F005
and a few T-bill marks, as they stood on 2026-11-06) plus only the static configuration of the real one (the
instrument registry and the capacity reference), so the next ids are always D003 and F006.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "tests/fixtures/ledger"
CONFIG_FILES = ("instruments.csv", "capacity_reference.csv")    # static configuration, not ledger contents


def seed_ledger(root: Path, marks: bool = True) -> Path:
    """Create ``root``/data/ledger from the frozen seed; returns ``root``."""
    led = root / "data/ledger"
    led.mkdir(parents=True, exist_ok=True)
    for f in CONFIG_FILES:
        shutil.copy(ROOT / "data/ledger" / f, led / f)
    for f in ("decisions.csv", "forecasts.csv") + (("marks.csv",) if marks else ()):
        shutil.copy(SEED / f, led / f)
    return root
