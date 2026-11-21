"""Manhattan's four research tracks (issue #102): separately identifiable, separately counted, dormant.
Synthetic declarations only: no data is read."""
from __future__ import annotations

import ast
import json
from datetime import time
from pathlib import Path

import pytest

from manhattan import tracks as T
from manhattan.marketdata.schema import Instrument

ROOT = Path(__file__).resolve().parents[1]


def _future(root):
    return Instrument(f"SYN:{root}", "future", "futures_daily", "America/Chicago", time(14, 0), "USD", root=root,
                      multiplier=1000.0, tick=0.015625)


def test_exactly_four_tracks_and_nothing_enabled():
    assert T.TRACK_IDS == ("commodities", "technology_equities", "non_technology_equities", "rates")
    assert tuple(T.TRACKS) == T.TRACK_IDS
    assert T.ENABLED is False and T.REAL_DATA is False
    assert all(t.status == "dormant_synthetic_only" for t in T.TRACKS.values())
    # the two equity tracks share one pipeline; the two futures tracks share theirs
    assert T.TRACKS["technology_equities"].pipeline == T.TRACKS["non_technology_equities"].pipeline == \
        ("manhattan.equities",)
    assert T.TRACKS["commodities"].pipeline == T.TRACKS["rates"].pipeline
    json.dumps(T.describe())                                               # reportable as plain data


def test_the_switches_are_constants_in_source():
    tree = ast.parse((ROOT / "manhattan/tracks.py").read_text(encoding="utf-8"))
    assigns = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign))
               for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
               if isinstance(t, ast.Name) and t.id in ("ENABLED", "REAL_DATA")]
    assert len(assigns) == 2 and all(isinstance(a.value, ast.Constant) and a.value.value is False for a in assigns)


def test_tally_reports_every_track_and_refuses_ambiguity():
    items = [{"track": "rates"}, {"track": "non_technology_equities"}, {"track": "non_technology_equities"}]
    r = T.tally(items)
    assert r["by_track"] == {"commodities": 0, "technology_equities": 0, "non_technology_equities": 2, "rates": 1}
    assert r["total"] == 3 and "combined_equities" in r["combinations_are_not_tracks"]
    for bad in ({}, {"track": "combined_equities"}, {"track": "bonds"},
                {"track": ["technology_equities", "non_technology_equities"]}):
        with pytest.raises(T.TrackError):
            T.tally([bad])


def test_treasury_futures_cash_bonds_and_bond_etfs_are_distinct():
    roots = {"SYNT": "treasury_future", "SYNC": "commodity_future"}
    assert T.rates_instrument_kind(_future("SYNT"), roots=roots) == "treasury_future"
    assert T.rates_instrument_kind(_future("SYNC"), roots=roots) == "commodity_future"
    with pytest.raises(T.TrackError):                                      # an undeclared root is never guessed
        T.rates_instrument_kind(_future("SYNX"), roots=roots)
    bond = Instrument("SYN:BOND", "bond_cash", "rates_daily", "America/New_York", time(17, 0), "USD",
                      price_basis="clean", maturity="2030-05-15", coupon=4.0)
    assert T.rates_instrument_kind(bond, roots=roots) == "cash_bond"
    fx = Instrument("SYN:EURUSD", "fx_spot", "fx_daily", "America/New_York", time(17, 0), "USD", base="EUR",
                    quote="USD")
    with pytest.raises(T.TrackError):
        T.rates_instrument_kind(fx, roots=roots)
    assert T.track_of_instrument_kind("treasury_future") == "rates"
    assert T.track_of_instrument_kind("cash_bond") is None                 # no track until decided (NT-4)
    assert T.track_of_instrument_kind("bond_etf") is None                  # no track (NT-5)
    assert T.INSTRUMENT_KINDS["bond_etf"].marketdata_asset_class is None   # the schema has no fund class
    assert "etf" in T.INSTRUMENT_KINDS["bond_etf"].equity_security_types
    assert T.TRACKS["rates"].instruments == ("treasury_future",)


def test_tracks_module_imports_nothing_that_could_run_or_read():
    tree = ast.parse((ROOT / "manhattan/tracks.py").read_text(encoding="utf-8"))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
        {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= {"__future__", "dataclasses", "types"}, mods
