"""Phase 4 readiness: the read-only development status, the held-out specification as data, and the fences.

Deterministic and cheap: no simulation is run, no held-out value is drawn, nothing under results/ is written.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from manhattan.sim import criteria_v2, dev_status, heldout_spec, run, runlog, world

ROOT = Path(__file__).resolve().parents[1]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text)


# ------------------------------------------------------------------------ the held-out specification as data

def test_every_heldout_scenario_is_listed_once():
    assert set(heldout_spec.SCENARIOS) == set(world.HELD_OUT) | set(criteria_v2.HEDGED_HELD_OUT)


@pytest.mark.parametrize("sid", sorted(heldout_spec.SCENARIOS))
def test_every_range_quotes_the_frozen_text_verbatim(sid):
    s = heldout_spec.SCENARIOS[sid]
    text = _norm((ROOT / s.source).read_text(encoding="utf-8"))
    row = next((r for r in text.split("\n| ") if r.startswith(f"{sid} |")), None) or \
        next((r for r in _norm_rows(ROOT / s.source) if r.startswith(f"| {sid} |")), "")
    assert row, f"{sid}: no table row in {s.source}"
    for p in s.params:
        assert _norm(p.quote) in row, f"{sid}: {p.quote!r} is not in its row of {s.source}"


def _norm_rows(path: Path) -> list[str]:
    return [_norm(line) for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("|")]


@pytest.mark.parametrize("sid", sorted(heldout_spec.SCENARIOS))
def test_numbers_of_a_range_appear_in_its_quote(sid):
    for p in heldout_spec.SCENARIOS[sid].params:
        q = p.quote.replace(",", "").replace("−", "-")
        for v in p.values:
            forms = {f"{v:g}", f"{v:g}".lstrip("0"), f"{int(v)}" if float(v).is_integer() else f"{v:g}",
                     f"{v * 100:g}%" if 0 < abs(v) < 1 else f"{v:g}",
                 f"{v * 100:g}-" if 0 < abs(v) < 1 else f"{v:g}"}                  # "1-5%": a percentage range
            if v == 0.5 and "half" in q:
                continue
            assert any(f in q for f in forms), f"{sid} {p.name}: {v} not in {p.quote!r}"


def test_construction_stays_disabled_while_anything_is_open():
    r = heldout_spec.readiness()
    assert heldout_spec.GENERAL
    assert not any(v["construction_allowed"] for v in r.values())
    assert all(v["open"][: len(heldout_spec.GENERAL)] == list(heldout_spec.GENERAL) for v in r.values())


def test_the_spec_module_draws_nothing():
    """No random generator, no seeds, no world: the table is data only."""
    tree = ast.parse((ROOT / "manhattan/sim/heldout_spec.py").read_text(encoding="utf-8"))
    names = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert names <= {"annotations", "dataclass", "field"} and mods <= {"__future__", "dataclasses"}


def test_only_seeds_defines_and_nothing_calls_the_heldout_generator():
    callers = []
    for p in (ROOT / "manhattan").rglob("*.py"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                f = n.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name == "heldout_rng":
                    callers.append(str(p.relative_to(ROOT)))
    assert callers == [], f"held-out values are drawn in {callers}"


# ------------------------------------------------------------------------ the fences around held-out runs

def test_heldout_refused_without_a_tagged_confirmation_run():
    clean = {"commit": "x", "dirty": False, "tags": []}
    with pytest.raises(runlog.HeldOutRefused):
        runlog.check_heldout(True, None, clean)
    with pytest.raises(runlog.HeldOutRefused):
        runlog.check_heldout(True, 1, clean)
    with pytest.raises(runlog.HeldOutRefused):
        runlog.check_heldout(True, 1, {"commit": "x", "dirty": True, "tags": ["manhattan-sim-confirm-1"]})


def test_h12_cannot_be_started(tmp_path):
    with pytest.raises(SystemExit, match="unknown scenario H12"):
        run.run_scenario("H12", "STD", 1, label="pilot", out=tmp_path, prereg_version="v2")
    assert not (tmp_path / "runs.jsonl").exists()


def test_heldout_worlds_are_not_coded():
    assert not set(heldout_spec.SCENARIOS) & set(world.SCENARIOS)


# ------------------------------------------------------------------------ the development status

def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_dev_status_on_an_empty_directory_decides_nothing(tmp_path):
    s = dev_status.build(tmp_path)
    assert {e["state"] for e in s["runs"]} == {"nothing on file"}
    assert s["criteria"] == []
    for g in s["screening_candidates"].values():
        assert g["eligible"] == "not determined" and g["state"] == "not decided"
    assert "DEVELOPMENT ONLY" in s["verdict_scope"] and "No screening method is selected" in s["verdict_scope"]
    assert s["held_out_runs_on_record"] == 0
    assert len(s["held_out"]) == len(heldout_spec.SCENARIOS)


def test_records_of_other_code_are_never_decided(tmp_path):
    """A full run of HB records made by other code is shown as other code only, and never as complete."""
    path = run.reps_path("D01", "HB", 0, tmp_path, "v2")
    _write(path, [{"rep": i, "code": "0000000000000000", "scenario": "D01", "size": "HB", "review_step": 63}
                  for i in range(400)])
    e = next(e for e in dev_status.inventory(tmp_path) if (e["scenario"], e["size"]) == ("D01", "HB"))
    assert e["state"] == "other code only" and e["on_file_current"] == 0
    assert e["other_code"] == [{"code": "0000000000000000", "review_step": 63, "replications": 400}]
    assert dev_status.criterion_rows(e, include_stale=False) == []


def test_records_of_another_review_step_do_not_count(tmp_path):
    code = run.code_hash("HB", version="v2")
    path = run.reps_path("D02", "HB", 0, tmp_path, "v2")
    _write(path, [{"rep": i, "code": code, "scenario": "D02", "size": "HB", "review_step": 252} for i in range(400)])
    e = next(e for e in dev_status.inventory(tmp_path) if (e["scenario"], e["size"]) == ("D02", "HB"))
    assert e["on_file_current"] == 0 and e["state"].startswith("other code only")


def test_missing_ranges_and_partial_runs(tmp_path):
    code = run.code_hash("STD", version="v2")
    path = run.reps_path("D04h", "STD", 0, tmp_path, "v2")
    _write(path, [{"rep": i, "code": code, "scenario": "D04h", "size": "STD"} for i in range(400) if not 172 <= i <= 203])
    e = next(e for e in dev_status.inventory(tmp_path) if e["scenario"] == "D04h")
    assert e["state"] == "incomplete" and e["on_file_current"] == 368 and e["missing_current"] == "172 to 203"


def test_twins_are_held_to_v3_only():
    assert dev_status.cr_required("V3", "D04h", "STD")
    for c in ("V1", "V2", "V4", "V5"):
        assert not dev_status.cr_required(c, "D04h", "STD")
    assert not dev_status.cr_required("V3", "D01", "HB") and not dev_status.cr_required("V5", "D01", "HB")
    assert dev_status.cr_required("V3", "D07a", "STD") and dev_status.cr_required("V12", "D10", "HB")


@pytest.mark.parametrize("verdict,category", [
    ("pass", "pass"), ("FAIL", "FAIL"), ("pilot: not decided (within threshold so far)", "not decided"),
    ("not evaluated: fewer than 200 observations", "not evaluated (small group)"), ("no data", "no data"),
    ("reported (within)", "reported")])
def test_verdict_categories(verdict, category):
    assert dev_status.classify(verdict) == category


def test_dev_status_is_deterministic_on_the_repository_records(tmp_path):
    a = dev_status.markdown(dev_status.build(run.OUT))
    b = dev_status.markdown(dev_status.build(run.OUT))
    assert a == b
    assert "No candidate is eligible or selected here" in a


# ------------------------------------------------------------------------ the HB code hash and manhattan/ledger.py

def test_hb_code_hash_covers_the_whole_ledger_module():
    """Recorded, not repaired: the HB code hash includes all of manhattan/ledger.py, so an operational edit of
    that file (as in commits 436b9fd, 135a035, 2e54231) makes every HB record on file uncountable."""
    assert "manhattan/ledger.py" in run.CODE_FILES_V2_HB


def test_the_model_reads_evidential_weight_with_its_default_reconstructed_flag():
    """The one ledger function the model calls gives the same reserve weights as before commit 436b9fd for the
    arguments the model passes (``reconstructed`` left at False)."""
    from manhattan.ledger import evidential_weight
    for channel in ("blind", "adaptive", "manual"):
        for designated in (False, True):
            before = 1 if (channel == "blind" and designated) else 0
            assert evidential_weight(channel, "reserve", designated) == before
    src = (ROOT / "manhattan/stats/hier_analytic.py").read_text(encoding="utf-8")
    assert 'evidential_weight(str(c), "reserve", bool(d))' in src
