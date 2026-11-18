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
    with pytest.raises(EvidenceError, match="not approved"):
        evidence.promote(evidence.ResearchRecord("pair_candidate", "ab" * 32), "promising", protocol_hash=fake,
                         config=cfg)
    monkeypatch.setattr(evidence, "EQUITY_RESEARCH_APPROVED", True)
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
    keys = [(catalogue.TIERS.index(catalogue.data_tier(f)[0]),
             -min(f["ranking"]["leakage_safety"], f["ranking"]["data_feasibility"])) for f in catalogue.prioritised(cat)]
    assert keys == sorted(keys)                      # affordable data tier first, then the leakage/data gate


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
        provenance.record("x", inputs={"prices": [1.0, 2.0]}, params={}, boundary={}, code_version="abc1234")
    with pytest.raises(EvidenceError, match="exploration"):
        provenance.record("x", inputs={}, params={}, boundary={}, code_version="abc1234", role="reserve")
    with pytest.raises(EvidenceError, match="git commit"):
        provenance.record("x", inputs={}, params={}, boundary={}, code_version="latest")
    with pytest.raises(EvidenceError, match="SHA-256"):
        evidence.ResearchRecord("pair_candidate", "not-a-hash")


# ----------------------------------------------------------------------------- integration contracts (S8 M9)
def test_s8_m9_method_name_only_objects_no_longer_satisfy_a_contract():
    """S8 M9: a fake with methods named start/finish passed as attempt accounting. Contracts are now exact
    signatures of the PR heads inspected, checked by parameter names and kinds."""
    import types

    def register_evaluation(ledger, *, identity, windows, caller, fence=None, freeze=None, holding=0, token=None,
                            supersedes=None):
        return None

    good = types.SimpleNamespace(register_evaluation=register_evaluation)
    assert integration.check("manhattan.access", "register_evaluation", module=good) == "structural_match"

    def start(*, executable, family, batch, spec_hash, data_hash, window, role):     # the old Protocol's shape
        return "id"
    bad = types.SimpleNamespace(register_evaluation=start)
    assert integration.check("manhattan.access", "register_evaluation", module=bad).startswith("mismatch")
    assert integration.check("manhattan.access", "register_evaluation", module=types.SimpleNamespace()) == "absent"

    def classify(metadata, verifications=None, *, fence, config=None, protocol_hash=None):
        return None
    assert integration.check("manhattan.evidence", "classify",
                             module=types.SimpleNamespace(classify=classify)) == "structural_match"


def test_s8_m9_interfaces_on_this_checkout_are_absent_or_match_never_mismatch():
    """On main today #84 and #86 are absent; once either merges this test checks its interface is still the one
    the equities adapters expect."""
    res = integration.check_all()
    assert all(v in ("absent", "structural_match") for v in res.values()), res
    assert integration.PINNED == {"#86": "bab1a4d", "#84": "e1882be"}


# ----------------------------------------------------------------------------- research gate (S8 H3, H4)
def test_s8_h3_real_data_research_is_refused_until_approved():
    assert evidence.EQUITY_RESEARCH_APPROVED is False
    synth = sources.ContractRegistry([sources.synthetic_contract("prices_daily")])
    evidence.require_research_scope(synth)
    public = sources.ContractRegistry([sources.DataContract(
        "edgar", "fundamentals_pit", "SEC", "public", "doc", "filing_acceptance_time", "vintaged", False,
        ("descriptive",))])
    with pytest.raises(EvidenceError, match="not approved"):
        evidence.require_research_scope(public)
    with pytest.raises(EvidenceError, match="declare"):
        evidence.require_research_scope(sources.ContractRegistry())


def test_s8_h3_scope_status_does_not_claim_pipeline_enforcement():
    st = evidence.scope_status(config=config.load())
    assert st["enforced_in_protected_pipeline"] is False
    assert any("protected pipeline" in p for p in st["prerequisites"])
    text = (ROOT / "docs/manhattan/equities/DESIGN.md").read_text(encoding="utf-8")
    assert "not integrated into Manhattan's protected pipeline" in text


def test_s8_h4_no_equity_module_or_test_constructs_a_window():
    for p in list(PKG.glob("*.py")) + list((ROOT / "tests").glob("test_manhattan_equities_*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
                assert name != "Window", f"{p.name}:{node.lineno} constructs a Window directly"


def test_s8_h4_research_entry_point_reads_through_a_reader_and_respects_roles():
    from datetime import date as D

    from manhattan import roles
    from manhattan.engine.pit import PitStore
    from manhattan.equities import pairs, pit_bridge, research
    from manhattan.equities import synthetic as syn
    w = syn.world()
    store = PitStore()
    reg = sources.ContractRegistry([sources.synthetic_contract("prices_daily")])
    pit_bridge.prices_to_pit(w.prices, store, reg.contract("prices_daily"), ["S01", "S02", "S07", "S08"],
                             D(2004, 1, 2), D(2007, 12, 31))
    fence = roles.Fence(exploration_end=D(2019, 12, 31), reserve={}, enabled=False)
    win = research.open_window(store, domain="us_tech_equities_synthetic", start=D(2004, 1, 2),
                               end=D(2007, 12, 31), fence=fence, contracts=reg)
    bd = pairs.Boundary(D(2004, 1, 5), D(2005, 12, 30), D(2006, 1, 4), D(2006, 12, 29))
    disc = research.discover_pairs(win, ["S01", "S02", "S07", "S08"], bd, pairs.PairRules(require_link=False),
                                   calendar=w.calendar)
    assert disc.attempts["considered"] == 6 == len(disc.result)
    # a reserve-dated read is refused by the existing role check (no attempt, not the runner)
    fence_r = roles.Fence(exploration_end=D(2005, 12, 31), reserve={"us_tech_equities_synthetic":
                                                                    (D(2006, 1, 2), D(2007, 12, 31))}, enabled=True)
    with pytest.raises(roles.RoleError):
        research.open_window(store, domain="us_tech_equities_synthetic", start=D(2006, 1, 3), end=D(2006, 6, 30),
                             fence=fence_r, contracts=reg)
    public = sources.ContractRegistry([sources.DataContract(
        "px", "prices_daily", "v", "public", "doc", "date_only", "immutable", False, ("descriptive",))])
    with pytest.raises(EvidenceError):
        research.open_window(store, domain="x", start=D(2004, 1, 2), end=D(2004, 6, 30), fence=fence, contracts=public)


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
               "manhattan.ops.promotion", "manhattan"}       # ``from manhattan import roles`` is module "manhattan"
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


# ----------------------------------------------------------------------------- catalogue: overlaps and data tiers
def test_s8_catalogue_shared_families_keep_ids_and_group_overlaps():
    cat = catalogue.load()
    ids = [f["id"] for f in cat["families"]]
    assert len(ids) == 39 and len(set(ids)) == 39            # nothing removed or renumbered
    groups = {}
    for f in cat["families"]:
        if f.get("shared_family"):
            groups.setdefault(f["shared_family"], set()).add(f["id"])
            assert catalogue.family_draft(f)["shared_family"] == f["shared_family"]
    assert {"TE-A03", "TE-C04"} <= groups["SF-REVISIONS"] and {"TE-A07", "TE-E01"} <= groups["SF-MOMENTUM"]
    assert all(len(m) >= 2 for m in groups.values())
    bad = dict(cat["families"][0], shared_family="SF-ALONE")
    assert any("at least two" in e for e in catalogue.validate({"status": "draft", "families": [bad]}))


def test_s8_catalogue_data_tiers_separate_runnable_from_blocked():
    tiers = {f["id"]: catalogue.data_tier(f) for f in catalogue.load()["families"]}
    assert all(t in catalogue.TIERS for t, _ in tiers.values())
    for fid, (t, blocks) in tiers.items():
        if t == "needs_unavailable_history":
            assert blocks, fid
    # families that need analyst estimates or borrow history can never be in the runnable tier
    for f in catalogue.load()["families"]:
        if {"analyst_estimates_pit", "borrow_availability"} & set(f["required_data"]):
            assert catalogue.data_tier(f)[0] == "needs_unavailable_history"
    assert sum(t == "prices_and_edgar" for t, _ in tiers.values()) >= 5


# ----------------------------------------------------------------------------- S8 final review: R2 and R3
def test_s8_r2_structure_is_not_runtime_integration():
    import types
    assert integration.runtime_integration() is False
    reqs = {name for _, name, _ in integration.SEMANTIC_REQUIREMENTS}
    assert {"bound_computation", "verified_fence", "config_record", "designated_reserve", "schema_v3",
            "attempt_object", "issued"} <= reqs
    # #86 restricts its runner-only paths to access/runner/data: equities pins and calls neither
    assert not any(p.split(".")[-1] in ("run_bound", "forward_window") for _, p in integration.EXPECTED)

    def verified_fence(commit, *, root=None, expected_sha256=None):
        return None
    mod = types.SimpleNamespace(verified_fence=verified_fence)
    assert integration.check("manhattan.access", "verified_fence", module=mod) == "structural_match"
    old = types.SimpleNamespace(SCHEMA="manhattan.evidence/2")
    assert integration.check_constant("manhattan.evidence", "SCHEMA", module=old).startswith("mismatch")
    assert integration.check_constant("manhattan.evidence", "SCHEMA",
                                      module=types.SimpleNamespace(SCHEMA="manhattan.evidence/3")) == "structural_match"
    md = integration.evidence_metadata_attempt("ab" * 32, "ledger")
    assert md == {"attempt": {"id": "ab" * 32, "store": "ledger"}} and "attempt_id" not in md


def test_s8_r3_priorities_follow_affordable_data_and_groups_are_declared_only():
    cat = catalogue.load()
    fams = {f["id"]: f for f in cat["families"]}
    assert len(fams) == 39                                           # the denominator is complete
    assert catalogue.data_tier(fams["TE-F01"])[0] == "prices_and_edgar"
    assert fams["TE-F01"]["optional_data"] == ["analyst_estimates_pit"]
    assert fams["TE-E07"]["shared_family"] == fams["TE-F02"]["shared_family"] == "SF-FINANCING"
    assert fams["TE-B03"]["shared_family"] == fams["TE-F04"]["shared_family"] == "SF-SEMI-CYCLE"
    order = catalogue.prioritised(cat)
    tiers = [catalogue.data_tier(f)[0] for f in order]
    assert tiers == sorted(tiers, key=catalogue.TIERS.index)
    d = catalogue.family_draft(fams["TE-E07"])
    assert d["shared_family_enforced"] is False
    doc = (ROOT / "docs/manhattan/equities/HYPOTHESIS_CATALOGUE.md").read_text(encoding="utf-8")
    assert "declared, not enforced" in doc and "Multiple-testing denominator" in doc


def test_equities_never_references_86s_private_access_paths():
    """PR #86 (bab1a4d; list first taken at 5aa643f) fails its own test if any module outside its allowlist references these names (as an
    identifier, attribute or exact string). The equities package must stay clean before and after #86 merges."""
    private = {"_open_window", "_SEAL_KEY", "_seal", "_GRANTS", "_fields", "_guard", "_Meter", "_meter", "_open_read",
               "_as_of", "_store", "_value", "_period", "diagnostic_window", "Window", "_CTX_KEY", "_PROOF_KEY", "_mac",
               "_store_mac", "_sealed_write", "_MINTED", "_BOUND", "_COMMIT_PENDING", "_settle_failed_commit",
               "_StoreBackend", "_LedgerBackend", "_completion_proof", "_mark_completed", "_backend",
               "_require_active", "_ended", "CompletionProof", "verify_completion", "store_seal_ok", "run_bound",
               "commit_results", "commit_failures", "commit_recovery", "forward_window", "record_evaluation",
               "_append", "_index", "_starts", "_terminated", "_superseded", "_designated", "_append_local",
               "_commit", "_push", "_transact", "_apply", "_verify_entry", "_reset_to_remote",
               # added at #86 bab1a4d
               "_COMPUTED", "_computing", "_may_read", "_FS_CACHE", "_check_forward_plan", "_tag", "_git_config",
               "_fence_of", "_fence_key"}
    for p in PKG.glob("*.py"):
        refs = set()
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Name):
                refs.add(node.id)
            elif isinstance(node, ast.Attribute):
                refs.add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                refs.add(node.value)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                refs.add(node.name)
            elif isinstance(node, ast.alias):
                refs.add(node.name.split(".")[-1])
        assert not (refs & private), f"{p.name} references {sorted(refs & private)}"


# ----------------------------------------------------------------------------- S8 targeted re-review: N1
def test_s8_n1_authorization_takes_config_and_the_old_shape_is_a_mismatch():
    """S8 N1: at #86 bab1a4d ``authorization`` takes ``config`` ({sha256, commit} or None), not ``config_sha256``.
    The checker must report the old shape as a mismatch (not be loosened to accept both)."""
    import types

    def new(kind, windows, *, caller, fence, freeze, holding, token, identity, config=None):
        return {}

    def old(kind, windows, *, caller, fence, freeze, holding, token, identity, config_sha256=None):
        return {}
    assert integration.check("manhattan.access", "authorization",
                             module=types.SimpleNamespace(authorization=new)) == "structural_match"
    assert integration.check("manhattan.access", "authorization",
                             module=types.SimpleNamespace(authorization=old)).startswith("mismatch")


def test_s8_n1_verified_fence_returns_the_capability_with_its_members():
    import types

    # this file, like manhattan/access.py, uses postponed annotations: these are recorded as strings, unevaluated
    def returns_capability(commit, *, root=None, expected_sha256=None) -> VerifiedFence:      # noqa: F821
        return None

    def returns_pair(commit, *, root=None, expected_sha256=None) -> tuple[roles.Fence, str]:   # noqa: F821
        return None
    assert integration.check_return("manhattan.access", "verified_fence",
                                    module=types.SimpleNamespace(verified_fence=returns_capability)) == "structural_match"
    assert integration.check_return("manhattan.access", "verified_fence",
                                    module=types.SimpleNamespace(verified_fence=returns_pair)).startswith("mismatch")

    class VerifiedFence:
        __slots__ = ("fence", "config_sha256", "commit")

        def valid(self):
            return True

        def record(self):
            return {}

    class NoRecord:
        __slots__ = ("fence", "config_sha256", "commit")

        def valid(self):
            return True
    assert integration.check_class_api("manhattan.access", "VerifiedFence",
                                       module=types.SimpleNamespace(VerifiedFence=VerifiedFence)) == "structural_match"
    assert integration.check_class_api("manhattan.access", "VerifiedFence",
                                       module=types.SimpleNamespace(VerifiedFence=NoRecord)).startswith("mismatch")


def test_s8_n1_structure_still_never_claims_runtime_integration():
    assert integration.runtime_integration() is False
    reqs = {name: text for _, name, text in integration.SEMANTIC_REQUIREMENTS}
    assert "VerifiedFence" in reqs["verified_fence"] and "config={sha256, commit}" in reqs["config_record"]
    assert set(integration.check_all()) >= {"manhattan.access:authorization", "manhattan.access:verified_fence->return",
                                            "manhattan.access:VerifiedFence.api"}
