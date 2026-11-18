"""Evidence classification (manhattan/evidence.py). Synthetic fixtures only: no market data is read.

Most tests run under a **simulated** authority (``TEST_AUTHORITY`` patched into ``TRUSTED_AUTHORITIES``) so that the
classification logic can be exercised. That proves the logic given authentic verifier results; it proves nothing
about the authenticity of any verifier result. The shipped value is checked in a clean subprocess, where no fixture
can patch it (``test_shipped_module_trusts_no_authority``), and a mutation test shows that check fails on a
non-empty shipped value.
"""
import ast
import copy
import dataclasses
import hashlib
import inspect
import random
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from manhattan import evidence as E, roles
from manhattan.ledger import evidential_weight

ROOT = Path(__file__).resolve().parents[1]
FENCE = roles.Fence(exploration_end=date(2019, 12, 31),
                    reserve={"fx_daily": (date(2020, 3, 2), date(2024, 12, 31))}, enabled=True)
CONFIG = {"reserve": {"enabled": True}, "claims": {"enabled": False}}
TEST_AUTHORITY = "simulated-test-authority"
H = lambda s: hashlib.sha256(s.encode()).hexdigest()
FWD0 = ("spec_registry", "publication_contract", "capture_replay", "store_anchor", "batch_freeze")
FWD = FWD0 + ("attempt_binding",)
PUB = ("spec_registry", "publication_contract", "public_archive")
LIC = ("spec_registry", "publication_contract", "licensed_snapshot")
RES = LIC + ("runner_token", "batch_freeze", "attempt_binding")
SYN = ("spec_registry", "synthetic_generator")


@pytest.fixture(autouse=True)
def simulated_authority(monkeypatch):
    monkeypatch.setattr(E, "TRUSTED_AUTHORITIES", frozenset({TEST_AUTHORITY}))


def contract(name="src", kind="daily_lag"):
    c = {"name": name, "frequency": "daily", "period_label": "observation_date",
         "availability": {"kind": kind, "reference": "synthetic fixture", "day_mapping": "close"}}
    if kind == "daily_lag":
        c["publication_lag_days"] = 1
    if kind == "conservative":
        c["availability"].update(assumption="a", owner_approval="b", release_history_unavailable="c")
    return c


def spec(channel="blind", freeze="2026-06-01", holding=0):
    return {"spec_hash": H("spec"), "channel": channel, "freeze": freeze, "holding_periods": holding}


def base(kind, start, end, vintage):
    return {"schema": E.SCHEMA, "source": {"id": "src", "kind": kind, "publication_contract": contract()},
            "domain": "fx_daily", "span": {"start": start, "end": end}, "vintage": vintage,
            "spec": spec(), "window": {"id": "w1"}, "designated": False}


def synthetic(**kw):
    md = base("synthetic", "2010-01-04", "2010-12-31", {"kind": "generated", "id": H("gen"), "as_of": "2010-12-31"})
    md.update(kw)
    return md


def historical(kind="public", start="2005-01-03", end="2019-12-31", avail="release_dates", **kw):
    md = base(kind, start, end, {"kind": "snapshot", "id": H("snap"), "as_of": "2026-11-01"})
    md["source"]["publication_contract"] = contract(kind=avail)
    md.update(kw)
    return md


def reserve(start="2021-01-04", end="2023-12-29", **kw):
    kw.setdefault("attempt", {"id": H("reserve attempt"), "store": "ledger"})
    kw.setdefault("designated", True)
    return historical("licensed", start=start, end=end, **kw)


def captured(start="2026-07-01", end="2026-10-30", backfill=0, late=0, monitoring="2026-06-15", **kw):
    kw.setdefault("attempt", {"id": H("attempt:" + start), "store": "store"})
    md = base("public", start, end, {"kind": "first_seen_capture", "id": H("cap"), "as_of": "2026-11-01"})
    md["capture"] = {"capture_id": H("cap"), "schema_version": 2, "monitoring_start": monitoring,
                     "first_retrieved_utc": monitoring + "T22:30:00+00:00",
                     "reconstructed": {"backfill": backfill, "late": late}}
    md.update(kw)
    return md


def _role(md, fence=FENCE):
    try:
        sp = md["spec"]
        freeze = None if sp["freeze"] is None else date.fromisoformat(sp["freeze"])
        return roles.role_of(date.fromisoformat(md["span"]["start"]), md["domain"], fence, freeze,
                             sp["holding_periods"])
    except Exception:
        return None


def facts_for(md):
    """What honest verifiers would state about ``md`` (built from the fixture, as a real verifier would not)."""
    sp, vin, cap = md.get("spec") or {}, md.get("vintage") or {}, md.get("capture") or {}
    rec, span, win = cap.get("reconstructed") or {}, md.get("span") or {}, md.get("window") or {}
    att, role = md.get("attempt") or {}, _role(md)
    observed = {"observed_start": span.get("start"), "observed_end": span.get("end")}
    snap = {"vintage_id": vin.get("id"), "as_of": vin.get("as_of"), **observed}
    return {
        "spec_registry": {"spec_hash": sp.get("spec_hash"), "channel": sp.get("channel"), "domain": md.get("domain"),
                          "holding_periods": sp.get("holding_periods")},
        "batch_freeze": {"spec_hash": sp.get("spec_hash"), "batch": "batch-0001", "freeze": sp.get("freeze"),
                         "manifest_hash": H("m")},
        "synthetic_generator": {"vintage_id": vin.get("id"), **observed},
        "publication_contract": {"source_id": md["source"]["id"],
                                 "contract_sha256": E.contract_digest(md["source"].get("publication_contract"))},
        "public_archive": snap, "licensed_snapshot": dict(snap),
        "capture_replay": {"source_id": md["source"]["id"], "capture_id": cap.get("capture_id"),
                           "monitoring_start": cap.get("monitoring_start"), "backfill": rec.get("backfill"),
                           "late": rec.get("late"), **observed},
        "store_anchor": {"capture_id": cap.get("capture_id"), "anchor": H("anchor"),
                         "assurance": E.INDEPENDENT_ANCHOR},
        "runner_token": {"domain": md.get("domain"), "window_id": win.get("id"), "batch": "batch-0001",
                         "manifest_hash": H("m"), "spec_hash": sp.get("spec_hash")},
        "attempt_binding": {"attempt_id": att.get("id"), "store": att.get("store"),
                            "kind": "forward_observation" if role == roles.FORWARD else "engine_evaluation",
                            "spec_hash": sp.get("spec_hash"), "role": role, "designated": md.get("designated"),
                            "window_id": win.get("id"), "window_start": span.get("start"),
                            "window_end": span.get("end"), "freeze": sp.get("freeze"),
                            "holding": sp.get("holding_periods"), "terminal": "completed", "superseded": False,
                            "assurance": E.INDEPENDENT_ANCHOR},
    }


def results(md, names, authority=TEST_AUTHORITY, subject=None, override=None):
    subject = subject or E.subject_digest(md)
    facts = facts_for(md)
    for (v, k), val in (override or {}).items():
        facts[v][k] = val
    return [E.VerifierResult(n, authority, subject, facts[n]) for n in names]


def run(md, names, fence=FENCE, config=CONFIG, override=None, **kw):
    return E.classify(md, results(md, names, override=override), fence=fence, config=config, **kw)


def assert_closed(c):
    assert type(c) is E.Classification
    assert c.provenance == E.UNVERIFIED and c.eligibility == E.E_NONE and c.weight_ceiling == 0
    assert c.problems and not c.authenticated
    assert_no_grant(c)


def assert_no_grant(c):
    assert c.forward_elond_eligible is False and c.screening_eligible is False and c.promotion_authorized is False
    assert c.blockers


# ---------------------------------------------------------------- N1: the shipped authority set, unpatched

_PROBE = """
import importlib.util, sys
sys.path.insert(0, sys.argv[2])
spec = importlib.util.spec_from_file_location("shipped_evidence_probe", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
value = mod.TRUSTED_AUTHORITIES
print(type(value).__name__, len(value))
"""


def shipped_authorities(module_path: Path) -> tuple[str, int]:
    """Import the module file in a clean, isolated interpreter (no pytest, no fixtures) and report the type and
    size of its ``TRUSTED_AUTHORITIES`` after the whole module has executed."""
    out = subprocess.run([sys.executable, "-I", "-c", _PROBE, str(module_path), str(ROOT)],
                         capture_output=True, text=True, timeout=120, check=True)
    kind, size = out.stdout.split()
    return kind, int(size)


def assert_ships_no_authority(module_path: Path) -> None:
    assert shipped_authorities(module_path) == ("frozenset", 0), "a trusted authority ships enabled"


def test_shipped_module_trusts_no_authority():
    assert_ships_no_authority(Path(E.__file__))


@pytest.mark.parametrize("mutation", [
    'TRUSTED_AUTHORITIES = frozenset({"anyone"})\n',                     # a plain reassignment (S6's mutation)
    'TRUSTED_AUTHORITIES |= {"anyone"}\n',
    'globals()["TRUSTED_AUTHORITIES"] = frozenset({"anyone"})\n',
    'TRUSTED_AUTHORITIES = {"anyone"}\n',                                # a non-frozen set
])
def test_shipped_authority_check_fails_on_a_non_empty_shipped_value(tmp_path, mutation):
    mutant = tmp_path / "evidence_mutant.py"
    mutant.write_text(Path(E.__file__).read_text(encoding="utf-8") + "\n" + mutation, encoding="utf-8")
    with pytest.raises(AssertionError, match="ships enabled"):
        assert_ships_no_authority(mutant)


def test_classification_is_unverified_with_the_shipped_set(monkeypatch):
    monkeypatch.setattr(E, "TRUSTED_AUTHORITIES", frozenset())
    for md, names in ((captured(), FWD), (reserve(), RES), (synthetic(), SYN)):
        c = E.classify(md, results(md, names), fence=FENCE, config=CONFIG)
        assert_closed(c)
        assert "not from a trusted authority" in c.problems[0]


# ---------------------------------------------------------------- H2: authority, not digests

def test_digest_alone_is_not_a_verification():
    md = captured()
    d = E.subject_digest(md)
    assert_closed(E.classify(md, {n: d for n in FWD}, fence=FENCE, config=CONFIG))
    assert_closed(E.classify(md, [d] * 6, fence=FENCE, config=CONFIG))


def test_untrusted_authority_is_rejected():
    md = captured()
    assert_closed(E.classify(md, results(md, FWD, authority="caller-said-so"), fence=FENCE, config=CONFIG))


def test_forged_freeze_date_cannot_make_a_forward_candidate():
    md = captured(spec=spec(freeze="2026-06-01"))
    assert run(md, FWD).eligibility == E.E_FORWARD
    forged = captured(spec=spec(freeze="2026-01-01"))
    c = run(forged, FWD, override={("batch_freeze", "freeze"): "2026-06-01"})
    assert_closed(c)
    assert "freeze date" in c.problems[0]


@pytest.mark.parametrize("verifier,key,value", [
    ("spec_registry", "spec_hash", H("other")), ("spec_registry", "channel", "adaptive"),
    ("spec_registry", "domain", "rates"), ("spec_registry", "holding_periods", 5),
    ("batch_freeze", "spec_hash", H("other")), ("batch_freeze", "manifest_hash", "x"), ("batch_freeze", "batch", ""),
    ("capture_replay", "capture_id", H("other")), ("capture_replay", "monitoring_start", "2026-06-01"),
    ("capture_replay", "backfill", 1), ("capture_replay", "late", 2), ("capture_replay", "source_id", "other"),
    ("store_anchor", "capture_id", H("other")), ("store_anchor", "anchor", "short"),
    ("store_anchor", "assurance", "trust me"),
    ("publication_contract", "contract_sha256", H("other")), ("publication_contract", "source_id", "other"),
])
def test_verified_facts_must_match_metadata(verifier, key, value):
    assert_closed(run(captured(), FWD, override={(verifier, key): value}))


def test_verification_bound_to_other_metadata_is_rejected():
    md = captured()
    edited = copy.deepcopy(md)
    edited["span"]["start"] = "2026-07-02"
    c = E.classify(edited, results(edited, FWD, subject=E.subject_digest(md)), fence=FENCE, config=CONFIG)
    assert_closed(c)
    assert "integrity" in c.problems[0]


@pytest.mark.parametrize("names", [FWD0[:-1] + FWD[-1:], FWD[1:], FWD + ("runner_token",), FWD + ("batch_freeze",),
                                   FWD + ("synthetic_generator",)])
def test_missing_extra_or_duplicate_results(names):
    assert_closed(run(captured(), names))


def test_result_with_wrong_fact_set_or_unknown_verifier():
    md = captured()
    rs = results(md, FWD)
    rs[0] = E.VerifierResult("spec_registry", TEST_AUTHORITY, rs[0].subject, {"spec_hash": H("spec")})
    assert_closed(E.classify(md, rs, fence=FENCE, config=CONFIG))
    rs = results(md, FWD) + [E.VerifierResult("trust_me", TEST_AUTHORITY, E.subject_digest(md), {})]
    assert_closed(E.classify(md, rs, fence=FENCE, config=CONFIG))


# ---------------------------------------------------------------- N5: verifier facts are immutable

def test_facts_are_copied_and_read_only():
    md = captured()
    facts = facts_for(md)
    live = facts["batch_freeze"]
    rs = [E.VerifierResult(n, TEST_AUTHORITY, E.subject_digest(md), facts[n]) for n in FWD]
    live["freeze"] = "2020-01-01"                                   # the caller's dict changes afterwards
    assert run(md, FWD) == E.classify(md, rs, fence=FENCE, config=CONFIG)
    assert E.classify(md, rs, fence=FENCE, config=CONFIG).eligibility == E.E_FORWARD
    with pytest.raises(TypeError):
        rs[0].facts["spec_hash"] = H("other")
    with pytest.raises(dataclasses.FrozenInstanceError):
        rs[0].facts = {}


@pytest.mark.parametrize("value", [[1], {"a": 1}, 1.5, b"x", {1, 2}, (1,)])
def test_non_scalar_facts_fail_closed(value):
    c = run(captured(), FWD, override={("store_anchor", "anchor"): value})
    assert_closed(c)
    assert "as scalars" in c.problems[0]


def test_non_mapping_facts_fail_closed():
    md = captured()
    rs = results(md, FWD)
    rs[0] = E.VerifierResult("spec_registry", TEST_AUTHORITY, rs[0].subject, [("spec_hash", H("spec"))])
    assert rs[0].facts is None
    assert_closed(E.classify(md, rs, fence=FENCE, config=CONFIG))


# ---------------------------------------------------------------- N4: forged Classification objects

def test_issued_classification_caps_and_combines():
    c = run(captured(), FWD)
    assert E.issued(c) and E.cap_weight(c, 1) == 1


def _forged():
    ident = E.Identity(H("spec"), "blind", "fx_daily", "2026-06-01", 0, "w1", "2026-07-01", "2026-10-30",
                       H("a"), "store", True)
    return E.Classification(E.CAPTURED_FORWARD, False, frozenset(), E.AVAIL_FIRST_SEEN, roles.FORWARD,
                            E.AUTH_FREEZE, E.E_FORWARD, 1, False, False, False, ("x",), (), H("s"), ident, True)


def test_caller_constructed_classification_gets_no_weight():
    forged = _forged()
    assert not E.issued(forged) and E.cap_weight(forged, 1) == 0
    assert_closed(E.combine([forged]))
    genuine = run(captured(start="2026-07-01", end="2026-07-31", window={"id": "w1"}), FWD)
    assert_closed(E.combine([genuine, forged]))


@pytest.mark.parametrize("derive", [
    lambda c: dataclasses.replace(c, weight_ceiling=1),
    lambda c: dataclasses.replace(c),
    copy.copy, copy.deepcopy,
])
def test_copies_of_issued_classifications_get_no_weight(derive):
    c = run(captured(late=1), FWD)                                  # ceiling 0
    d = derive(c)
    assert E.cap_weight(d, 1) == 0
    assert_closed(E.combine([d]))


def test_mutated_issued_classification_gets_no_weight():
    c = run(captured(late=1), FWD)
    assert E.issued(c)
    object.__setattr__(c, "weight_ceiling", 1)
    object.__setattr__(c, "eligibility", E.E_FORWARD)
    assert not E.issued(c) and E.cap_weight(c, 1) == 0
    assert_closed(E.combine([c]))


def test_registry_does_not_change_outputs_or_leak():
    import gc
    md = captured()
    before = len(E._ISSUED)
    for _ in range(50):
        assert run(md, FWD) == run(copy.deepcopy(md), FWD)
    gc.collect()
    assert len(E._ISSUED) <= before + 2


# ---------------------------------------------------------------- N2: observed span inside a verified window

@pytest.mark.parametrize("verifier", ["capture_replay"])
@pytest.mark.parametrize("key,value", [("observed_start", "2026-07-02"), ("observed_end", "2026-10-29"),
                                       ("observed_start", "2026-06-30")])
def test_observed_dates_must_be_the_span(verifier, key, value):
    c = run(captured(), FWD, override={(verifier, key): value})
    assert_closed(c)
    assert "observed date" in c.problems[0]


@pytest.mark.parametrize("make,names,verifier", [
    (lambda: historical(), PUB, "public_archive"), (lambda: reserve(), RES, "licensed_snapshot"),
    (lambda: synthetic(), SYN, "synthetic_generator")])
def test_observed_dates_bind_every_provenance(make, names, verifier):
    assert_closed(run(make(), names, override={(verifier, "observed_end"): "2009-01-01"}))


@pytest.mark.parametrize("w0,w1,ok", [
    ("2026-07-01", "2026-10-30", True), ("2026-06-02", "2026-11-06", True),       # cumulative window (PR #86)
    ("2026-07-02", "2026-10-30", False), ("2026-07-01", "2026-10-29", False), ("2026-08-01", "2026-09-01", False)])
def test_span_must_lie_inside_the_verified_window(w0, w1, ok):
    c = run(captured(), FWD, override={("attempt_binding", "window_start"): w0,
                                       ("attempt_binding", "window_end"): w1})
    if ok:
        assert c.eligibility == E.E_FORWARD and c.identity.window_verified
    else:
        assert_closed(c)
        assert "outside the attempt's verified window" in c.problems[0]


def test_reserve_span_must_lie_inside_the_verified_window():
    assert_closed(run(reserve(), RES, override={("attempt_binding", "window_end"): "2023-06-30"}))


# ---------------------------------------------------------------- N3: reserve token bound to spec and batch

def test_designated_reserve_candidate_needs_token_freeze_and_attempt():
    c = run(reserve(), RES)
    assert (c.role, c.authorization, c.eligibility, c.weight_ceiling) == (
        roles.RESERVE, E.AUTH_RESERVE, E.E_RESERVE, 1)
    for drop in ("runner_token", "batch_freeze", "attempt_binding"):
        assert_closed(run(reserve(), tuple(n for n in RES if n != drop)))
    md = reserve()
    del md["attempt"]
    c = run(md, RES)
    assert_closed(c)
    assert "must name its registered attempt" in c.problems[0]


@pytest.mark.parametrize("key,value", [("spec_hash", H("another spec")), ("batch", "batch-0002"),
                                       ("manifest_hash", H("another manifest")), ("window_id", "w2"),
                                       ("domain", "rates")])
def test_token_of_another_spec_batch_or_window_is_rejected(key, value):
    c = run(reserve(), RES, override={("runner_token", key): value})
    assert_closed(c)
    assert "token" in c.problems[0]


@pytest.mark.parametrize("key,value", [("kind", "screening"), ("kind", "forward_observation"),
                                       ("designated", False), ("role", roles.FORWARD), ("spec_hash", H("x")),
                                       ("store", "store"), ("attempt_id", H("other attempt"))])
def test_reserve_attempt_binding_must_match(key, value):
    assert_closed(run(reserve(), RES, override={("attempt_binding", key): value}))


# ---------------------------------------------------------------- PR #86 contracts

@pytest.mark.parametrize("terminal,superseded", [("failed", False), ("aborted", False), (None, False),
                                                 ("completed", True), ("completed", None)])
def test_only_completed_non_superseded_attempts_carry_evidence(terminal, superseded):
    c = run(captured(), FWD, override={("attempt_binding", "terminal"): terminal,
                                       ("attempt_binding", "superseded"): superseded})
    assert_closed(c)


def test_attempt_holding_must_be_the_specs_never_a_default():
    md = captured(spec=spec(holding=5))
    assert run(md, FWD).eligibility == E.E_FORWARD
    c = run(md, FWD, override={("attempt_binding", "holding"): 0})       # PR #86's default
    assert_closed(c)
    assert "never a default" in c.problems[0]


def test_registration_freeze_after_the_manifest_moves_the_forward_start():
    md = captured(start="2026-07-01")
    c = run(md, FWD, override={("attempt_binding", "freeze"): "2026-06-20"})
    assert c.eligibility == E.E_FORWARD and c.identity.freeze == "2026-06-20"
    c = run(md, FWD, override={("attempt_binding", "freeze"): "2026-07-15"})        # registered after the span starts
    assert_closed(c)
    assert "registration freeze" in c.problems[0]
    c = run(md, FWD, override={("attempt_binding", "freeze"): "2026-05-01"})        # before the manifest freeze
    assert_closed(c)
    assert "precedes the manifest freeze" in c.problems[0]
    assert_closed(run(md, FWD, override={("attempt_binding", "freeze"): None}))


def test_ledger_and_store_attempt_ids_are_namespaced():
    # PR #86: engine evaluations live in the Ledger, forward observations and screening in the Store
    md = captured(attempt={"id": H("a"), "store": "ledger"})
    assert run(md, FWD, override={("attempt_binding", "kind"): "engine_evaluation"}).eligibility == E.E_FORWARD
    c = run(md, FWD)                                                # a forward_observation claimed from the Ledger
    assert_closed(c)
    assert "registered in the store" in c.problems[0]
    c = run(captured(), FWD, override={("attempt_binding", "kind"): "engine_evaluation"})
    assert_closed(c)
    assert "registered in the ledger" in c.problems[0]
    assert_closed(run(captured(), FWD, override={("attempt_binding", "store"): "ledger"}))
    assert_closed(run(captured(attempt={"id": H("a"), "store": "both"}), FWD))
    assert_closed(run(captured(attempt={"id": H("a")}), FWD))


@pytest.mark.parametrize("verifier", ["store_anchor", "attempt_binding"])
def test_supplied_anchor_is_not_independent_certification(verifier):
    c = run(captured(), FWD, override={(verifier, "assurance"): E.SUPPLIED_ANCHOR})
    assert c.provenance == E.CAPTURED_FORWARD and c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0
    assert any("supplied anchor" in b for b in c.blockers)
    c = run(reserve(), RES, override={("attempt_binding", "assurance"): E.SUPPLIED_ANCHOR})
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0


def test_forward_capture_without_attempt_binding_is_descriptive_only():
    md = captured()
    del md["attempt"]
    c = run(md, FWD0)
    assert c.provenance == E.CAPTURED_FORWARD and c.genuine_capture and not c.identity.window_verified
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0
    assert any("attempt binding" in b for b in c.blockers)


def test_attempt_identity_needs_attempt_binding():
    assert_closed(run(captured(), FWD0))
    assert_closed(run(captured(attempt={"id": "not-a-hash", "store": "store"}), FWD))


# ---------------------------------------------------------------- legitimate classification (simulated authority)

def test_synthetic_validates_infrastructure_only():
    c = run(synthetic(), SYN)
    assert (c.provenance, c.availability, c.eligibility, c.weight_ceiling) == (
        E.SYNTHETIC, E.AVAIL_GENERATED, E.E_INFRA, 0)
    assert c.role == roles.EXPLORATION and c.authenticated
    assert any("never market performance" in b for b in c.blockers)
    assert_no_grant(c)


def test_synthetic_on_forward_dates_is_still_infrastructure_only():
    md = synthetic(span={"start": "2026-07-01", "end": "2026-10-30"},
                   vintage={"kind": "generated", "id": H("g"), "as_of": "2026-10-30"})
    c = run(md, SYN + ("batch_freeze",))
    assert c.role == roles.FORWARD and c.eligibility == E.E_INFRA and c.weight_ceiling == 0


def test_historical_public_exploration_is_descriptive():
    c = run(historical(), PUB)
    assert (c.provenance, c.licensed, c.role, c.authorization, c.eligibility, c.weight_ceiling) == (
        E.HISTORICAL_PUBLIC, False, roles.EXPLORATION, E.AUTH_OPEN, E.E_DESCRIPTIVE, 0)
    assert c.availability == E.AVAIL_PER_VINTAGE and not c.reconstruction


def test_historical_licensed_is_high_quality_but_not_forward_evidence():
    c = run(historical("licensed", start="2026-07-01", end="2026-10-30"), LIC + ("batch_freeze",))
    assert c.provenance == E.HISTORICAL_LICENSED and c.licensed and c.role == roles.FORWARD
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0 and not c.genuine_capture
    assert any("not captured forward evidence" in b for b in c.blockers)


def test_licensed_designated_reserve_is_a_screening_candidate_only():
    c = run(reserve(), RES)
    assert c.weight_ceiling == evidential_weight("blind", "reserve", True, False) == 1
    assert any("never independent forward confirmation" in b for b in c.blockers)
    assert_no_grant(c)


@pytest.mark.parametrize("change,avail", [({"spec": spec("adaptive")}, "release_dates"),
                                          ({}, "daily_lag"), ({}, "conservative")])
def test_reserve_candidate_requirements(change, avail):
    md = reserve(**change)
    md["source"]["publication_contract"] = contract(kind=avail)
    c = run(md, RES)
    assert c.provenance == E.HISTORICAL_LICENSED
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0


def test_undesignated_reserve_read_is_unauthorised():
    md = reserve(designated=False)
    c = run(md, LIC + ("attempt_binding",))
    assert c.role == roles.RESERVE and c.authorization == E.AUTH_NONE and c.eligibility == E.E_NONE


def test_reserve_disabled_in_config_authorises_nothing():
    c = run(reserve(), RES, config={"reserve": {"enabled": False}})
    assert c.authorization == E.AUTH_NONE and c.eligibility == E.E_NONE and c.weight_ceiling == 0


def test_genuine_capture_is_forward_candidate_but_never_elond_eligible():
    c = run(captured(), FWD)
    assert c.genuine_capture and c.provenance == E.CAPTURED_FORWARD and c.authenticated
    assert (c.role, c.authorization, c.eligibility, c.weight_ceiling) == (
        roles.FORWARD, E.AUTH_FREEZE, E.E_FORWARD, 1)
    for gate in E.UNIMPLEMENTED_GATES:
        assert gate in c.blockers
    assert any("necessary, not sufficient" in b for b in c.blockers)
    assert "promotion disabled: no_adopted_protocol" in c.blockers
    assert_no_grant(c)


def test_capture_with_promotion_config_enabled_still_grants_nothing():
    c = run(captured(), FWD, config={"reserve": {"enabled": True}, "claims": {"enabled": True}},
            protocol_hash=H("protocol"))
    assert c.eligibility == E.E_FORWARD
    assert_no_grant(c)


def test_licensed_captured_forward_keeps_licence_flag():
    md = captured()
    md["source"]["kind"] = "licensed"
    c = run(md, FWD)
    assert c.provenance == E.CAPTURED_FORWARD and c.licensed and c.eligibility == E.E_FORWARD


# ---------------------------------------------------------------- M1: holding-period embargo

BOUND_FENCE = roles.Fence(exploration_end=date(2020, 12, 31),
                          reserve={"fx_daily": (date(2020, 6, 1), date(2020, 11, 30))}, enabled=True)


def _bday(d, n):
    return np.busday_offset(np.datetime64(d), n, roll="forward").astype(object)


def _edge_days(h):
    start, end = date(2020, 6, 1), date(2020, 11, 30)
    days = {start, end, date(2020, 5, 29)}
    for k in (h, h + 1, h + 2):
        days.add(_bday(start, -k))
        days.add(_bday(end, -k))
    return sorted(days)


@pytest.mark.parametrize("h", [0, 5, 20])
def test_holding_period_embargo_matches_role_of_at_every_edge(h):
    for day in _edge_days(h):
        md = historical("licensed", start=day.isoformat(), end=day.isoformat(), spec=spec(holding=h))
        expected = roles.role_of(day, "fx_daily", BOUND_FENCE, date(2026, 6, 1), h)
        c = run(md, LIC, fence=BOUND_FENCE)
        assert c.role == expected, (h, day)
        if expected == roles.EMBARGO:
            assert c.eligibility == E.E_NONE and c.weight_ceiling == 0


@pytest.mark.parametrize("h", [0, 5, 20])
def test_holding_period_designated_reserve_edges(h):
    end = date(2020, 11, 30)
    for k in range(0, 25):
        day = _bday(end, -k).isoformat()
        c = run(reserve(start=day, end=day, spec=spec(holding=h)), RES, fence=BOUND_FENCE)
        embargoed = roles.role_of(_bday(end, -k), "fx_daily", BOUND_FENCE, date(2026, 6, 1), h) == roles.EMBARGO
        if embargoed:
            assert_closed(c)
        else:
            assert c.eligibility == E.E_RESERVE and c.weight_ceiling == 1
        assert embargoed == (k < h + 1), (h, k)


def test_regression_holding_zero_no_longer_assumed():
    day = _bday(date(2024, 12, 31), -10).isoformat()
    assert run(reserve(end=day, spec=spec(holding=0)), RES).eligibility == E.E_RESERVE
    c = run(reserve(end=day, spec=spec(holding=20)), RES)
    assert_closed(c)
    assert "several roles" in c.problems[0]


@pytest.mark.parametrize("bad", [None, -1, True, 1.0, "5", 10**9, [5]])
def test_unknown_or_malformed_holding_fails_closed(bad):
    md = captured()
    md["spec"]["holding_periods"] = bad
    assert_closed(E.classify(md, [], fence=FENCE, config=CONFIG))


def test_missing_holding_fails_closed():
    md = captured()
    del md["spec"]["holding_periods"]
    assert_closed(E.classify(md, [], fence=FENCE, config=CONFIG))


def test_contradictory_holding_fails_closed():
    c = run(reserve(), RES, override={("spec_registry", "holding_periods"): 20})
    assert_closed(c)
    assert "holding period" in c.problems[0]


# ---------------------------------------------------------------- M2: malformed config, fence, protocol hash

BAD_CONFIGS = [{"reserve": True}, {"reserve": None}, {"reserve": []}, {"reserve": "on"},
               {"reserve": {"enabled": "yes"}}, {"reserve": {"enabled": 1}}, {"claims": True},
               {"claims": []}, {"claims": {"enabled": "true"}}, {"claims": {"enabled": None}},
               "config", 5, [], ["reserve"], True]


@pytest.mark.parametrize("cfg", BAD_CONFIGS)
def test_malformed_config_fails_closed(cfg):
    for md, names in ((captured(), FWD), (reserve(), RES), (synthetic(), SYN)):
        assert_closed(run(md, names, config=cfg))


@pytest.mark.parametrize("ph", [123, "abc", b"x" * 32, H("p").upper(), ["x"]])
def test_malformed_protocol_hash_fails_closed(ph):
    assert_closed(run(captured(), FWD, protocol_hash=ph))


@pytest.mark.parametrize("fence", [None, "fence", {"exploration_end": "2019-12-31"},
                                   roles.Fence(exploration_end="2019-12-31", reserve={}),
                                   roles.Fence(exploration_end=date(2019, 12, 31), reserve={"fx_daily": "x"}),
                                   roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled="yes")])
def test_malformed_fence_fails_closed(fence):
    assert_closed(run(captured(), FWD, fence=fence))


def _junk(rng, depth=0):
    choices = [None, True, False, 0, -1, 1.5, float("inf"), "", "x", "2026-07-01", H("j"), [], {}, (1,), b"b"]
    if depth < 2:
        choices += [[_junk(rng, depth + 1)], {"enabled": _junk(rng, depth + 1)},
                    {"reserve": _junk(rng, depth + 1), "claims": _junk(rng, depth + 1)}]
    return rng.choice(choices)


def test_fuzz_config_and_promotion_settings_never_raise():
    rng = random.Random(84)
    md = captured()
    for _ in range(600):
        cfg = {"reserve": _junk(rng), "claims": _junk(rng)} if rng.random() < 0.7 else _junk(rng)
        ph = _junk(rng) if rng.random() < 0.5 else None
        c = run(md, FWD, config=cfg, protocol_hash=ph)
        assert type(c) is E.Classification
        assert_no_grant(c)
        assert c.weight_ceiling in (0, 1)


def _leaves(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _leaves(v, path + (k,))
    yield path


def test_fuzz_metadata_mutations_never_raise_or_grant():
    rng = random.Random(86)
    for make, names in ((captured, FWD), (reserve, RES), (synthetic, SYN)):
        original = make()
        baseline = run(original, names)
        paths = [p for p in _leaves(original) if p]
        for _ in range(250):
            md = copy.deepcopy(original)
            path = rng.choice(paths)
            target = md
            for k in path[:-1]:
                target = target[k]
            if rng.random() < 0.2:
                del target[path[-1]]
            else:
                target[path[-1]] = _junk(rng)
            try:
                rebound = E.subject_digest(md)
            except E.EvidenceError:
                rebound = None
            rs = results(original, names, subject=rebound) if rebound and rng.random() < 0.5 else results(
                original, names)
            c = E.classify(md, rs, fence=FENCE, config=CONFIG)
            assert type(c) is E.Classification
            assert_no_grant(c)
            if md != original and c.eligibility in (E.E_RESERVE, E.E_FORWARD):
                # verified facts were stated about the original: only a change they do not cover may survive,
                # and it may not change the identity or the ceiling
                assert c.identity == baseline.identity and c.weight_ceiling == baseline.weight_ceiling, path


# ---------------------------------------------------------------- reconstructed / backfilled

@pytest.mark.parametrize("kw,reason", [({"backfill": 3}, E.BACKFILLED), ({"late": 1}, E.LATE)])
def test_reconstructed_capture_is_explicit_and_weightless(kw, reason):
    c = run(captured(**kw), FWD)
    assert c.provenance == E.CAPTURED_FORWARD and reason in c.reconstruction and not c.genuine_capture
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0


def test_conservative_availability_capture_is_reconstructed():
    md = captured()
    md["source"]["publication_contract"] = contract(kind="conservative")
    c = run(md, FWD)
    assert E.CONSERVATIVE in c.reconstruction and c.availability == E.AVAIL_CONSERVATIVE
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0


def test_backfilled_history_masquerading_as_captured_forward():
    c = run(captured(start="2026-06-02", monitoring="2026-09-01"), FWD)
    assert_closed(c)
    assert "posing as captured" in c.problems[0]


def test_backfill_reported_honestly_is_flagged_not_rejected():
    c = run(captured(start="2026-06-02", monitoring="2026-09-01", backfill=60), FWD)
    assert E.BACKFILLED in c.reconstruction and c.weight_ceiling == 0


def test_snapshot_vintage_with_capture_block_fails_closed():
    md = captured()
    md["vintage"]["kind"] = "snapshot"
    assert_closed(run(md, PUB + ("batch_freeze", "attempt_binding")))


def test_capture_vintage_without_capture_block():
    md = captured()
    del md["capture"]
    assert_closed(run(md, FWD))


def test_recent_dates_alone_never_make_captured_forward():
    c = run(historical("public", start="2026-07-01", end="2026-10-30"), PUB + ("batch_freeze",))
    assert c.provenance == E.HISTORICAL_PUBLIC and c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0


# ---------------------------------------------------------------- adversarial metadata

def test_missing_source_definition():
    md = captured()
    del md["source"]["publication_contract"]
    assert_closed(E.classify(md, [], fence=FENCE, config=CONFIG))


@pytest.mark.parametrize("mutate", [
    lambda c: c.update(frequency="monthly"),
    lambda c: c["availability"].update(kind="guess"),
    lambda c: c["availability"].update(reference=""),
    lambda c: c.update(publication_lag_days=-1),
    lambda c: c.update(name="other"),
    lambda c: c.pop("period_label"),
])
def test_invalid_publication_contract(mutate):
    md = captured()
    mutate(md["source"]["publication_contract"])
    assert_closed(E.classify(md, [], fence=FENCE, config=CONFIG))


@pytest.mark.parametrize("mutate", [
    lambda m: m["span"].update(start="2026-11-02"),
    lambda m: m["span"].update(end="2026-11-20"),
    lambda m: m["capture"].update(first_retrieved_utc="2026-01-01T00:00:00+00:00"),
    lambda m: m["capture"].update(monitoring_start="2026-11-05", first_retrieved_utc="2026-11-05T00:00:00+00:00"),
    lambda m: m["capture"].update(first_retrieved_utc="2026-06-15T22:30:00"),
    lambda m: m["span"].update(start="2026-02-30"),
    lambda m: m["span"].update(start=20260701),
    lambda m: m["spec"].update(freeze="2026-08-01"),
])
def test_inconsistent_dates(mutate):
    md = captured()
    mutate(md)
    assert_closed(run(md, FWD))


@pytest.mark.parametrize("mutate", [
    lambda m: m["capture"].update(capture_id=H("other")),
    lambda m: m["capture"].update(capture_id="abc"),
    lambda m: m["capture"].pop("capture_id"),
    lambda m: m["capture"].update(schema_version=1),
    lambda m: m["capture"].update(schema_version=True),
])
def test_unknown_capture_identity(mutate):
    md = captured()
    mutate(md)
    assert_closed(run(md, FWD))


@pytest.mark.parametrize("label", [roles.FORWARD, roles.RESERVE, "confirmatory"])
def test_forged_role_label(label):
    assert_closed(run(historical("licensed", claimed_role=label), LIC))


def test_true_role_label_is_accepted_but_changes_nothing():
    a, b = run(historical(), PUB), run(historical(claimed_role=roles.EXPLORATION), PUB)
    assert (a.provenance, a.eligibility, a.weight_ceiling) == (b.provenance, b.eligibility, b.weight_ceiling)


def test_forged_provenance_label():
    assert_closed(run(historical(claimed_provenance=E.CAPTURED_FORWARD), PUB))


@pytest.mark.parametrize("extra", [{"evidential_weight": 1}, {"eligible": True}, {"filename": "captured_forward.csv"},
                                   {"provenance": E.CAPTURED_FORWARD}, {"tier": "formally_supported"},
                                   {"holding_periods": 0}, {"attempt_id": H("a")}])
def test_unknown_fields_fail_closed(extra):
    md = historical()
    md.update(extra)
    assert_closed(run(md, PUB))


def test_designated_outside_reserve_is_forged():
    assert_closed(run(captured(designated=True), RES))


@pytest.mark.parametrize("mutate", [
    lambda m: m["vintage"].update(id=[H("a"), H("b")]),
    lambda m: m["vintage"].update(id=None),
    lambda m: m["vintage"].update(id="latest"),
    lambda m: m["vintage"].pop("as_of"),
    lambda m: m["vintage"].update(kind="mixed"),
])
def test_ambiguous_vintage(mutate):
    md = historical()
    mutate(md)
    assert_closed(run(md, PUB))


@pytest.mark.parametrize("drop", [
    lambda m: m.pop("source"), lambda m: m.pop("span"), lambda m: m.pop("vintage"), lambda m: m.pop("designated"),
    lambda m: m.pop("schema"), lambda m: m.update(schema="manhattan.evidence/2"), lambda m: m.pop("spec"),
    lambda m: m.pop("window"), lambda m: m["window"].update(id=""),
    lambda m: m["capture"].pop("reconstructed"), lambda m: m["capture"]["reconstructed"].pop("late"),
    lambda m: m["capture"]["reconstructed"].update(late=-1), lambda m: m["spec"].pop("freeze"),
    lambda m: m["source"].update(kind="vendor"), lambda m: m.update(domain=""),
])
def test_incomplete_metadata(drop):
    md = captured()
    drop(md)
    assert_closed(E.classify(md, [], fence=FENCE, config=CONFIG))


@pytest.mark.parametrize("bad", [None, [], "captured_forward", 3, {"schema": E.SCHEMA, "x": float("nan")},
                                 {1: "non-text key"}])
def test_non_metadata_fails_closed(bad):
    assert_closed(E.classify(bad, [], fence=FENCE, config=CONFIG))


def test_embargo_and_disabled_reserve():
    c = run(historical(start="2020-01-02", end="2020-01-10"), PUB)
    assert c.role == roles.EMBARGO and c.eligibility == E.E_NONE and c.weight_ceiling == 0
    off = roles.Fence(exploration_end=date(2019, 12, 31), reserve=FENCE.reserve, enabled=False)
    c = run(historical("licensed", start="2021-01-04", end="2021-02-26"), LIC, fence=off)
    assert c.role == roles.EMBARGO and c.eligibility == E.E_NONE


def test_span_across_fence_fails_closed():
    assert_closed(run(historical(start="2019-06-03", end="2021-06-30"), PUB))


# ---------------------------------------------------------------- M3: combine identity

def _part(start, end, window, attempt=None, **kw):
    if attempt:
        kw["attempt"] = {"id": attempt, "store": "store"}
    return run(captured(start=start, end=end, window={"id": window}, **kw), FWD)


def test_combine_disjoint_parts_of_one_spec_keeps_every_part():
    a, b = _part("2026-07-01", "2026-07-31", "w1"), _part("2026-08-03", "2026-08-31", "w2")
    c = E.combine([a, b])
    assert c.eligibility == E.E_FORWARD and c.parts == (a, b) and c.subjects == (a.subject, b.subject)
    assert [p.provenance for p in c.parts] == [E.CAPTURED_FORWARD] * 2
    assert E.issued(c) and E.cap_weight(c, 1) == 1
    assert_no_grant(c)


def test_combine_rejects_duplicates():
    a = _part("2026-07-01", "2026-07-31", "w1")
    assert_closed(E.combine([a, a]))
    assert_closed(E.combine([a, _part("2026-08-03", "2026-08-31", "w1")]))
    x, y = _part("2026-07-01", "2026-07-31", "w1", H("a")), _part("2026-08-03", "2026-08-31", "w2", H("a"))
    assert_closed(E.combine([x, y]))


def test_combine_rejects_the_same_attempt_id_across_stores():
    x = _part("2026-07-01", "2026-07-31", "w1", H("a"))
    md = captured(start="2026-08-03", end="2026-08-31", window={"id": "w2"}, attempt={"id": H("a"), "store": "ledger"})
    y = run(md, FWD, override={("attempt_binding", "kind"): "engine_evaluation"})
    assert y.eligibility == E.E_FORWARD
    assert_closed(E.combine([x, y]))


def test_combine_rejects_overlapping_spans():
    a, b = _part("2026-07-01", "2026-07-31", "w1"), _part("2026-07-31", "2026-08-31", "w2")
    assert_closed(E.combine([a, b]))


@pytest.mark.parametrize("other", [
    {"spec": {**spec(), "spec_hash": H("other spec")}}, {"spec": spec("adaptive")},
    {"spec": spec(freeze="2026-05-01")}, {"spec": spec(holding=5)}])
def test_combine_rejects_other_specs_channels_freezes_holdings(other):
    a = _part("2026-07-01", "2026-07-31", "w1")
    b = _part("2026-08-03", "2026-08-31", "w2", **other)
    assert b.eligibility == E.E_FORWARD
    assert_closed(E.combine([a, b]))


def test_combine_rejects_other_domain():
    a = run(historical(start="2005-01-03", end="2009-12-31"), PUB)
    b = run(historical(start="2010-01-04", end="2014-12-31", window={"id": "w2"}, domain="rates"), PUB)
    assert b.provenance == E.HISTORICAL_PUBLIC
    assert_closed(E.combine([a, b]))


def test_combine_attempt_identity_all_or_none():
    a = _part("2026-07-01", "2026-07-31", "w1", H("a1"))
    b = _part("2026-08-03", "2026-08-31", "w2", H("a2"))
    assert E.combine([a, b]).eligibility == E.E_FORWARD
    md = captured(start="2026-08-03", end="2026-08-31", window={"id": "w2"})
    del md["attempt"]
    assert_closed(E.combine([a, run(md, FWD0)]))


def test_mixed_provenance_fails_closed():
    a = _part("2026-07-01", "2026-07-31", "w1")
    b = run(historical("licensed", start="2026-08-03", end="2026-08-31", window={"id": "w2"}),
            LIC + ("batch_freeze",))
    assert_closed(E.combine([a, b]))
    assert_closed(E.combine([a, run(synthetic(window={"id": "w3"}), SYN)]))
    assert_closed(E.combine([a, E.classify({}, [], fence=FENCE)]))
    assert_closed(E.combine([]))
    assert_closed(E.combine(None))
    assert_closed(E.combine([a, "classification"]))


def test_combine_takes_the_weakest_part():
    good, recon = _part("2026-07-01", "2026-07-31", "w1"), _part("2026-08-03", "2026-08-31", "w2", late=2)
    c = E.combine([good, recon])
    assert c.provenance == E.CAPTURED_FORWARD and E.LATE in c.reconstruction
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0
    assert c.parts[0].weight_ceiling == 1


# ---------------------------------------------------------------- weight and purity

CASES = [
    lambda: run(synthetic(), SYN), lambda: run(historical(), PUB), lambda: run(historical("licensed"), LIC),
    lambda: run(reserve(), RES), lambda: run(captured(), FWD),
    lambda: run(captured(late=1), FWD), lambda: run(captured(), ()),
]


@pytest.mark.parametrize("make", CASES)
@pytest.mark.parametrize("recorded", [0, 1, 2, -1, True, None])
def test_classification_never_upgrades_weight(make, recorded):
    c = make()
    capped = E.cap_weight(c, recorded)
    assert capped in (0, 1)
    assert capped <= (recorded if type(recorded) is int and recorded in (0, 1) else 0)
    assert capped <= c.weight_ceiling
    assert_no_grant(c)


def test_cap_weight_rejects_non_classifications():
    assert E.cap_weight("forward_candidate", 1) == 0


TABLE_6_3 = {  # ARCHITECTURE section 6.3: (channel, role, designated, reconstructed) -> weight
    (c, r, d, x): (1 if (r == "reserve" and c == "blind" and d and not x) or (r == "forward" and not x) else 0)
    for c in ("blind", "adaptive") for r in ("exploration", "reserve", "forward")
    for d in (False, True) for x in (False, True)}


@pytest.mark.parametrize("key", sorted(TABLE_6_3))
def test_existing_evidential_weight_table_unchanged(key):
    assert evidential_weight(*key) == TABLE_6_3[key]


@pytest.mark.parametrize("make", CASES)
def test_ceiling_is_a_value_of_the_existing_table(make):
    c = make()
    if c.eligibility in (E.E_RESERVE, E.E_FORWARD):
        assert c.weight_ceiling == evidential_weight("blind", c.role, c.role == "reserve", bool(c.reconstruction))
    else:
        assert c.weight_ceiling == 0


def test_module_is_pure():
    tree = ast.parse(inspect.getsource(E))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert mods <= {"__future__", "hashlib", "json", "re", "weakref", "dataclasses", "datetime", "types", "typing",
                    "numpy", "manhattan", "manhattan.availability", "manhattan.ledger", "manhattan.ops"}, mods
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls & {"open", "exec", "eval", "__import__"}


def test_classification_is_deterministic():
    md = captured()
    assert run(md, FWD) == run(copy.deepcopy(md), FWD)
