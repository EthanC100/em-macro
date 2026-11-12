"""Atlas: the simulation pre-registration is frozen, and config/atlas.yaml is valid.

docs/atlas/SIM_PREREG.md was committed with its SHA-256 (docs/atlas/sim_prereg.sha256) before any simulation code
existed. It is never edited; a change without a matching hash fails here.

Tests gate existing writers (.claude/agents/implementer.md): systematic-monthly runs the whole suite before it
commits the rebalance. The two checks below that read hand-edited files on main therefore follow the repository's
convention: they FAIL in every Claude Code session and wherever NIGHT_SHIFT_STRICT=1 (pr-review, promote) or
ATLAS_STRICT=1 is set, and SKIP with a message inside a GitHub Actions workflow that sets neither, so that an
Atlas document can never stop an existing writer. The unit tests of the checking code always run.
"""
import os
from pathlib import Path

import pytest

from atlas import config as AC
from atlas import prereg as AP

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "docs/atlas/SIM_PREREG.md"
RECORD = ROOT / "docs/atlas/sim_prereg.sha256"


def _strict() -> bool:
    env = os.environ
    in_writer_workflow = env.get("GITHUB_ACTIONS") == "true"
    return not in_writer_workflow or env.get("NIGHT_SHIFT_STRICT") == "1" or env.get("ATLAS_STRICT") == "1"


def _fail_or_skip(problems: list[str]) -> None:
    if not problems:
        return
    msg = "; ".join(problems)
    if _strict():
        pytest.fail(msg)
    pytest.skip(f"Atlas check failed, skipped in a writer's workflow (set ATLAS_STRICT=1 to enforce): {msg}")


# ---- the frozen pre-registration ----

def test_sim_prereg_hash_matches():
    assert AP.RECORDS == (RECORD,)
    _fail_or_skip(AP.verify(RECORD))


def test_sim_prereg_record_names_the_file():
    rows = AP.read_record(RECORD)
    _fail_or_skip([] if [rel for _, rel in rows] == ["docs/atlas/SIM_PREREG.md"]
                  else [f"sim_prereg.sha256 must record exactly docs/atlas/SIM_PREREG.md, found {rows}"])


def _copy(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "docs/atlas").mkdir(parents=True)
    doc, rec = tmp_path / "docs/atlas/SIM_PREREG.md", tmp_path / "docs/atlas/sim_prereg.sha256"
    doc.write_text("# frozen\n\nthreshold 0.22\n", encoding="utf-8")
    rec.write_text(f"{AP.sha256(doc)}  docs/atlas/SIM_PREREG.md\n", encoding="utf-8")
    return doc, rec


def test_verify_accepts_an_unchanged_file(tmp_path):
    _, rec = _copy(tmp_path)
    assert AP.verify(rec, root=tmp_path) == []


def test_verify_detects_an_edit(tmp_path):
    doc, rec = _copy(tmp_path)
    doc.write_text(doc.read_text(encoding="utf-8").replace("0.22", "0.25"), encoding="utf-8")   # a weakened threshold
    errs = AP.verify(rec, root=tmp_path)
    assert len(errs) == 1 and "never edited" in errs[0]


def test_verify_detects_a_missing_file_and_a_bad_record(tmp_path):
    doc, rec = _copy(tmp_path)
    doc.unlink()
    assert AP.verify(rec, root=tmp_path) == ["docs/atlas/SIM_PREREG.md: missing"]
    rec.write_text("not a hash  docs/atlas/SIM_PREREG.md\n", encoding="utf-8")
    assert "line 1" in AP.verify(rec, root=tmp_path)[0]
    rec.write_text("\n", encoding="utf-8")
    assert "records no file" in AP.verify(rec, root=tmp_path)[0]


def test_hash_is_the_labs_file_hash(tmp_path):
    # reuse, not a second implementation: the same function freezes Lab sleeves (lab/book.py)
    from lab import book
    assert AP.sha256 is book.sha256


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    doc, rec = _copy(tmp_path)
    monkeypatch.setattr(AP, "RECORDS", (rec,))
    monkeypatch.setattr(AP, "ROOT", tmp_path)
    assert AP.main(["verify"]) == 0 and "ok" in capsys.readouterr().out
    doc.write_text("changed\n", encoding="utf-8")
    assert AP.main(["verify"]) == 1 and "never edited" in capsys.readouterr().out
    assert AP.main(["something-else"]) == 2


# ---- config/atlas.yaml ----

def test_atlas_config_on_disk_is_valid():
    _fail_or_skip(AC.validate(AC.load()))


def _defaults() -> dict:
    return {"freeze": {"authority": "ethan_only"},
            "reserve": {"enabled": False, "mode": "shared_window", "evaluate_adaptive": False, "store": "imac_only",
                        "windows": {}},
            "exploration": {"data_end": "2019-12-31"},
            "forward": {"real_money": False, "loss_cap_usd": 0},
            "programme": {"end": None},
            "levels": {"screening_fdr": 0.20, "forward_fdr": 0.05},
            "claims": {"enabled": False, "screening_method": None},
            "trial_ledger": {"count_in_trials_csv": False}}


def test_conservative_defaults_validate():
    assert AC.validate(_defaults()) == []


def test_real_money_is_always_refused():
    cfg = _defaults()
    cfg["forward"]["real_money"] = True
    assert any("real_money" in e for e in AC.validate(cfg))


def test_a_reserve_needs_a_fence():
    cfg = _defaults()
    cfg["reserve"]["enabled"] = True
    assert any("fence" in e for e in AC.validate(cfg))
    cfg["reserve"]["windows"] = {"fx_daily": {"start": "2020-01-01", "end": "2026-09-30"}}
    assert AC.validate(cfg) == []
    cfg["reserve"]["windows"] = {"fx_daily": {"start": "2026-09-30", "end": "2020-01-01"}}
    assert any("start before end" in e for e in AC.validate(cfg))


def test_levels_cannot_be_loosened():
    cfg = _defaults()
    cfg["levels"]["screening_fdr"] = 0.25
    assert any("screening_fdr" in e for e in AC.validate(cfg))
    cfg = _defaults()
    cfg["levels"]["forward_fdr"] = 0.10
    assert any("forward_fdr" in e for e in AC.validate(cfg))
    cfg = _defaults()
    cfg["levels"].update(screening_fdr=0.10, forward_fdr=0.01)       # stricter is allowed
    assert AC.validate(cfg) == []


def test_claims_need_a_method_chosen_by_the_simulation():
    cfg = _defaults()
    cfg["claims"]["enabled"] = True
    assert any("simulation" in e for e in AC.validate(cfg))
    cfg["claims"]["screening_method"] = "ebh_elond"
    assert AC.validate(cfg) == []
    cfg["claims"]["screening_method"] = "bonferroni"
    assert any("screening_method" in e for e in AC.validate(cfg))


def test_missing_sections_are_reported():
    errs = AC.validate({})
    assert "freeze.authority is required" in errs and "claims.enabled is required" in errs


def test_strict_everywhere_but_a_writers_workflow(monkeypatch):
    for k in ("GITHUB_ACTIONS", "NIGHT_SHIFT_STRICT", "ATLAS_STRICT"):
        monkeypatch.delenv(k, raising=False)
    assert _strict()                                    # a Claude Code session, a laptop
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert not _strict()                                # systematic-monthly, ledger-daily
    monkeypatch.setenv("NIGHT_SHIFT_STRICT", "1")
    assert _strict()                                    # promote, pr-review
    monkeypatch.delenv("NIGHT_SHIFT_STRICT")
    monkeypatch.setenv("ATLAS_STRICT", "1")
    assert _strict()                                    # a future Atlas workflow
