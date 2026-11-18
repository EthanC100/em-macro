"""Technology equities: the evidence boundary, the hypothesis catalogue, provenance, integration contracts and the
package's isolation (no network, no real data, no writes, no edits to existing Manhattan code)."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from manhattan import config
from manhattan import spec as S
from manhattan.equities import catalogue, evidence, integration, provenance, sources
from manhattan.equities.errors import EvidenceError
from manhattan.ops import promotion

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "manhattan/equities"


# ----------------------------------------------------------------------------- evidence
@pytest.mark.parametrize("tier", promotion.TIERS)
@pytest.mark.parametrize("kind", evidence.CANDIDATE_KINDS)
def test_no_research_output_can_be_promoted(kind, tier):
    rec = evidence.ResearchRecord(kind, "ab" * 32)
    with pytest.raises(EvidenceError):
        evidence.promote(rec, tier, config=config.load())


def test_promotion_stays_shut_even_if_manhattan_gate_opened(monkeypatch):
    fake = "cd" * 32
    monkeypatch.setattr(promotion, "ADOPTED_PROTOCOLS", frozenset({fake}))
    cfg = {"claims": {"enabled": True}}
    st = evidence.scope_status(protocol_hash=fake, config=cfg)
    assert not st["open"] and any("single equities" in r for r in st["reasons"])
    with pytest.raises(EvidenceError, match="single equities"):
        evidence.promote(evidence.ResearchRecord("pair_candidate", "ab" * 32), "promising", protocol_hash=fake,
                         config=cfg)
    # with both gates open, a candidate is still not what gets promoted
    monkeypatch.setattr(evidence, "EQUITY_COVERING_PROTOCOLS", frozenset({fake}))
    with pytest.raises(EvidenceError, match="frozen family"):
        evidence.promote(evidence.ResearchRecord("pair_candidate", "ab" * 32), "promising", protocol_hash=fake,
                         config=cfg)
    with pytest.raises(EvidenceError, match="never evidence"):
        evidence.promote(evidence.ResearchRecord("synthetic_test", "ab" * 32), "promising", protocol_hash=fake,
                         config=cfg)


def test_equity_scope_is_empty_and_records_carry_zero_weight():
    assert evidence.EQUITY_COVERING_PROTOCOLS == frozenset()
    with pytest.raises(EvidenceError):
        evidence.ResearchRecord("pair_candidate", "ab" * 32, evidential_weight=1)
    with pytest.raises(EvidenceError):
        evidence.ResearchRecord("backtest_result", "ab" * 32)
    st = evidence.scope_status(config=config.load())
    assert not st["open"] and len(st["prerequisites"]) >= 5


# ----------------------------------------------------------------------------- catalogue
def test_catalogue_validates_and_is_large_and_balanced():
    cat = catalogue.load()
    assert catalogue.validate(cat) == []
    fams = cat["families"]
    assert len(fams) >= 30
    for rf in catalogue.RESEARCH_FAMILIES:
        assert sum(f["research_family"] == rf for f in fams) >= 4
    for ap in catalogue.APPROACHES:
        assert sum(f["approach"] == ap for f in fams) >= 10


def test_catalogue_entries_are_valid_unfrozen_family_drafts():
    for f in catalogue.load()["families"]:
        d = catalogue.family_draft(f)
        assert S.validate_family(d) == []
        assert d["status"] == "draft" and d["catalogue_id"] == f["id"]
    ids = [S.spec_id(catalogue.family_draft(f)) for f in catalogue.load()["families"]]
    assert len(set(ids)) == len(ids)


def test_catalogue_validation_catches_bad_entries():
    cat = catalogue.load()
    bad = dict(cat["families"][0])
    bad["required_data"] = ["prices_daily", "crystal_ball"]
    bad["ranking"] = dict(bad["ranking"], data_feasibility=7)
    bad["rationale"] = "It earned 12% a year."
    errs = catalogue.validate({"status": "draft", "families": [bad, cat["families"][0]]})
    joined = " ".join(errs)
    assert "crystal_ball" in joined and "1 to 5" in joined and "performance" in joined and "duplicate" in joined
    assert catalogue.validate({"status": "final", "families": []})


def test_priority_order_is_deterministic_and_gated_by_leakage_and_data():
    cat = catalogue.load()
    order = [f["id"] for f in catalogue.prioritised(cat)]
    assert order == [f["id"] for f in catalogue.prioritised(catalogue.load())]
    gates = [min(f["ranking"]["leakage_safety"], f["ranking"]["data_feasibility"]) for f in catalogue.prioritised(cat)]
    assert gates == sorted(gates, reverse=True)


def test_rendered_catalogue_document_is_in_sync():
    doc = ROOT / "docs/manhattan/equities/HYPOTHESIS_CATALOGUE.md"
    assert doc.read_text(encoding="utf-8") == catalogue.render(catalogue.load()) + "\n", \
        "run: python -m manhattan.equities.catalogue render --out docs/manhattan/equities/HYPOTHESIS_CATALOGUE.md"


# ----------------------------------------------------------------------------- provenance
def test_provenance_hash_is_deterministic_and_value_free():
    reg = sources.ContractRegistry([sources.synthetic_contract("prices_daily")])
    kw = dict(inputs={"prices": "aa" * 32}, params={"lookback": 252}, boundary={"formation_end": date(2006, 6, 30)},
              code_version="abc1234", contracts=reg)
    a, b = provenance.record("pair_candidate", **kw), provenance.record("pair_candidate", **kw)
    assert a == b and a["id"].startswith("EQ-") and provenance.verify(a)
    a2 = dict(a, params={"lookback": 126})
    assert not provenance.verify(a2)
    with pytest.raises(EvidenceError, match="SHA-256"):
        provenance.record("x", inputs={"prices": [1.0, 2.0]}, params={}, boundary={}, code_version="x")
    with pytest.raises(EvidenceError, match="exploration"):
        provenance.record("x", inputs={}, params={}, boundary={}, code_version="x", role="reserve")


# ----------------------------------------------------------------------------- integration contracts
def test_integration_contracts_are_checkable_without_the_unfinished_code():
    class Attempts:
        def start(self, *, executable, family, batch, spec_hash, data_hash, window, role):
            return "id"

        def finish(self, attempt_id, *, result_hash, status):
            return None

    assert integration.conforms(Attempts(), "attempts")
    assert not integration.conforms(object(), "attempts")
    assert set(integration.CONTRACTS) == {"attempts", "evidence", "simulation", "execution_costs", "portfolio"}


# ----------------------------------------------------------------------------- isolation
def _modules():
    return sorted(PKG.glob("*.py"))


def test_package_has_no_network_or_vendor_imports():
    banned = {"requests", "urllib", "http", "socket", "yfinance", "pandas_datareader", "databento", "norgatedata",
              "subprocess"}
    for p in _modules():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module.split(".")[0]]
            assert not (set(names) & banned), f"{p.name} imports {set(names) & banned}"


def test_package_reads_no_repository_data_and_writes_only_where_asked():
    for p in _modules():
        text = p.read_text(encoding="utf-8")
        for needle in ("data/ledger", "data/janus", "em-macro-data", "EM_MACRO_DATA", "results/", "data/processed"):
            assert needle not in text, f"{p.name} mentions {needle}"
        if p.name != "catalogue.py":            # catalogue render --out writes the file it is told to
            assert "write_text" not in text and "open(" not in text, f"{p.name} writes files"


def test_package_imports_only_existing_manhattan_modules_and_never_unfinished_ones():
    allowed = {"manhattan.spec", "manhattan.availability", "manhattan.engine.pit", "manhattan.ops",
               "manhattan.ops.promotion", "manhattan"}
    for p in _modules():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and \
                    node.module.startswith("manhattan") and not node.module.startswith("manhattan.equities"):
                assert node.module in allowed, f"{p.name} imports {node.module}"


def test_catalogue_yaml_carries_no_retired_project_name():
    # test_manhattan_prereg.py forbids the retired name in Python and docs, not in YAML; the needle is built from two
    # parts so that this file itself passes that test.
    retired = "at" + "las"
    assert retired not in (PKG / "catalogue.yaml").read_text(encoding="utf-8").lower()
