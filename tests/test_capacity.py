"""Capacity checks (ledger/capacity.py): diagnostic only for the frozen algorithm."""
import math

from ledger import capacity as C


def test_square_root_impact_and_flags():
    ref = {"X": {"adv_usd_m": 1000.0, "contract_multiplier": None, "position_limit_contracts": None,
                 "default_ann_vol_pct": 10.0},
           "F": {"adv_usd_m": 100000.0, "contract_multiplier": 1000.0, "position_limit_contracts": 6000.0,
                 "default_ann_vol_pct": 30.0}}
    r = C.check("X", 50.0, 500e6, ref)               # 250m notional against 1bn ADV
    assert r["pct_adv"] == 25.0 and r["flags"] == ["adv"]
    expect = 0.10 / math.sqrt(252) * math.sqrt(0.25)
    assert r["impact_bp_full"] == round(expect * 1e4, 1)
    ok = C.check("X", 10.0, 500e6, ref)              # 50m: 5% of ADV
    assert ok["flags"] == [] and ok["pct_adv"] == 5.0
    f = C.check("F", 100.0, 500e6, ref, price=100.0)  # 5,000 contracts of a 6,000 limit
    assert f["contracts"] == 5000 and "limit" in f["flags"]
    cap = C.max_notional("F", ref, price=100.0)
    assert C.check("F", 100 * cap / 500e6, 500e6, ref, price=100.0)["flags"] == []


def test_capital_schedule_c01_c03():
    assert C.algo_capital("2026-11") == 100_000.0
    assert C.algo_capital("2026-12") == 500_000_000.0 == C.JANUS_CAPITAL


def test_reference_covers_the_algorithm_universe():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    design = json.loads((root / "results/systematic/fit/frozen_design.json").read_text())
    ref = C.load_reference()
    for inst in set(design["instruments"]["fx"]) | set(design["instruments"]["bond"]):
        assert inst in ref and ref[inst]["adv_usd_m"] and ref[inst]["adv_status"]
