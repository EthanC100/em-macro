"""Evidence classification (manhattan/evidence.py). Synthetic fixtures only: no market data is read.

Most tests run under a **simulated** authority (``TEST_AUTHORITY`` patched into ``TRUSTED_AUTHORITIES``) so that
the classification logic can be exercised. That proves the logic given authentic verifier results; it proves
nothing about the authenticity of any verifier result. With the module as shipped no authority is trusted and
every classification is unverified (``test_shipped_module_trusts_no_authority``).
"""
import ast
import copy
import hashlib
import inspect
import random
from datetime import date

import numpy as np
import pytest

from manhattan import evidence as E, roles
from manhattan.ledger import evidential_weight

FENCE = roles.Fence(exploration_end=date(2019, 12, 31),
                    reserve={"fx_daily": (date(2020, 3, 2), date(2024, 12, 31))}, enabled=True)
CONFIG = {"reserve": {"enabled": True}, "claims": {"enabled": False}}
TEST_AUTHORITY = "simulated-test-authority"
H = lambda s: hashlib.sha256(s.encode()).hexdigest()
FWD0 = ("spec_registry", "publication_contract", "capture_replay", "store_anchor", "batch_freeze")
FWD = FWD0 + ("attempt_binding",)
PUB = ("spec_registry", "publication_contract", "public_archive")
LIC = ("spec_registry", "publication_contract", "licensed_snapshot")
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


def base(kind, start, end, vintage, **kw):
    md = {"schema": E.SCHEMA, "source": {"id": "src", "kind": kind, "publication_contract": contract()},
          "domain": "fx_daily", "span": {"start": start, "end": end}, "vintage": vintage,
          "spec": spec(), "window": {"id": "w1"}, "designated": False}
    md.update(kw)
    return md


def synthetic(**kw):
    md = base("synthetic", "2010-01-04", "2010-12-31",
              {"kind": "generated", "id": H("gen"), "as_of": "2010-12-31"})
    md.update(kw)
    return md


def historical(kind="public", start="2005-01-03", end="2019-12-31", avail="release_dates", **kw):
    md = base(kind, start, end, {"kind": "snapshot", "id": H("snap"), "as_of": "2026-11-01"}, **kw)
    md["source"]["publication_contract"] = contract(kind=avail)
    return md


def reserve(**kw):
    return historical("licensed", start="2021-01-04", end="2023-12-29", designated=True, **kw)


def captured(start="2026-07-01", end="2026-10-30", backfill=0, late=0, monitoring="2026-06-15", **kw):
    kw.setdefault("attempt_id", H("attempt:" + start))
    md = base("public", start, end, {"kind": "first_seen_capture", "id": H("cap"), "as_of": "2026-11-01"}, **kw)
    md["capture"] = {"capture_id": H("cap"), "schema_version": 2, "monitoring_start": monitoring,
                     "first_retrieved_utc": monitoring + "T22:30:00+00:00",
                     "reconstructed": {"backfill": backfill, "late": late}}
    return md


def facts_for(md):
    """What honest verifiers would state about ``md`` (built from the fixture, as a real verifier would not)."""
    sp, vin, cap = md.get("spec") or {}, md.get("vintage") or {}, md.get("capture") or {}
    rec = cap.get("reconstructed") or {}
    snap = {"vintage_id": vin.get("id"), "as_of": vin.get("as_of")}
    return {
        "spec_registry": {"spec_hash": sp.get("spec_hash"), "channel": sp.get("channel"), "domain": md.get("domain"),
                          "holding_periods": sp.get("holding_periods")},
        "batch_freeze": {"spec_hash": sp.get("spec_hash"), "freeze": sp.get("freeze"), "manifest_hash": H("m")},
        "synthetic_generator": {"vintage_id": vin.get("id")},
        "publication_contract": {"source_id": md["source"]["id"],
                                 "contract_sha256": E.contract_digest(md["source"].get("publication_contract"))},
        "public_archive": snap, "licensed_snapshot": dict(snap),
        "capture_replay": {"source_id": md["source"]["id"], "capture_id": cap.get("capture_id"),
                           "monitoring_start": cap.get("monitoring_start"), "backfill": rec.get("backfill"),
                           "late": rec.get("late")},
        "store_anchor": {"capture_id": cap.get("capture_id"), "anchor": H("anchor")},
        "runner_token": {"domain": md.get("domain"), "window_id": (md.get("window") or {}).get("id"),
                         "manifest_hash": H("m")},
        "attempt_binding": {"attempt_id": md.get("attempt_id"), "spec_hash": sp.get("spec_hash"),
                            "window_id": (md.get("window") or {}).get("id")},
    }


def results(md, names, authority=TEST_AUTHORITY, subject=None, override=None):
    subject = subject or E.subject_digest(md)
    facts = facts_for(md)
    for (v, k), val in (override or {}).items():
        facts[v][k] = val
    return [E.VerifierResult(n, authority, subject, facts[n]) for n in names]


def run(md, names, fence=FENCE, config=CONFIG, **kw):
    return E.classify(md, results(md, names), fence=fence, config=config, **kw)


def assert_closed(c):
    assert type(c) is E.Classification
    assert c.provenance == E.UNVERIFIED and c.eligibility == E.E_NONE and c.weight_ceiling == 0
    assert c.problems and not c.authenticated
    assert_no_grant(c)


def assert_no_grant(c):
    assert c.forward_elond_eligible is False and c.screening_eligible is False and c.promotion_authorized is False
    assert c.blockers


# ---------------------------------------------------------------- H2: authority, not digests

def test_shipped_module_trusts_no_authority(monkeypatch):
    tree = ast.parse(inspect.getsource(E))
    shipped = [n.value for n in ast.walk(tree) if isinstance(n, ast.AnnAssign)
               and getattr(n.target, "id", None) == "TRUSTED_AUTHORITIES"]
    assert len(shipped) == 1 and ast.unparse(shipped[0]) == "frozenset()"
    monkeypatch.setattr(E, "TRUSTED_AUTHORITIES", frozenset())        # as shipped
    for md, names in ((captured(), FWD), (reserve(), LIC + ("runner_token",)), (synthetic(), SYN)):
        c = E.classify(md, results(md, names), fence=FENCE, config=CONFIG)
        assert_closed(c)
        assert "not from a trusted authority" in c.problems[0]


def test_digest_alone_is_not_a_verification():
    md = captured()
    d = E.subject_digest(md)
    assert_closed(E.classify(md, {n: d for n in FWD}, fence=FENCE, config=CONFIG))   # the old interface
    assert_closed(E.classify(md, [d] * 5, fence=FENCE, config=CONFIG))


def test_untrusted_authority_is_rejected():
    md = captured()
    c = E.classify(md, results(md, FWD, authority="caller-said-so"), fence=FENCE, config=CONFIG)
    assert_closed(c)


def test_forged_freeze_date_cannot_make_a_forward_candidate():
    # historical data from 2026 relabelled as frozen earlier: the authority states the real freeze
    md = captured(spec=spec(freeze="2026-06-01"))
    assert run(md, FWD).eligibility == E.E_FORWARD
    forged = captured(spec=spec(freeze="2026-01-01"))
    c = E.classify(forged, results(forged, FWD, override={("batch_freeze", "freeze"): "2026-06-01"}),
                   fence=FENCE, config=CONFIG)
    assert_closed(c)
    assert "freeze date" in c.problems[0]


@pytest.mark.parametrize("verifier,key,value", [
    ("spec_registry", "spec_hash", H("other")), ("spec_registry", "channel", "adaptive"),
    ("spec_registry", "domain", "rates"), ("spec_registry", "holding_periods", 5),
    ("batch_freeze", "spec_hash", H("other")), ("batch_freeze", "manifest_hash", "x"),
    ("capture_replay", "capture_id", H("other")), ("capture_replay", "monitoring_start", "2026-06-01"),
    ("capture_replay", "backfill", 1), ("capture_replay", "late", 2), ("capture_replay", "source_id", "other"),
    ("store_anchor", "capture_id", H("other")), ("store_anchor", "anchor", "short"),
    ("publication_contract", "contract_sha256", H("other")), ("publication_contract", "source_id", "other"),
])
def test_verified_facts_must_match_metadata(verifier, key, value):
    md = captured()
    c = E.classify(md, results(md, FWD, override={(verifier, key): value}), fence=FENCE, config=CONFIG)
    assert_closed(c)


@pytest.mark.parametrize("verifier,key,value", [
    ("runner_token", "window_id", "w2"), ("runner_token", "domain", "rates"),
    ("licensed_snapshot", "vintage_id", H("x")), ("licensed_snapshot", "as_of", "2026-10-01")])
def test_verified_reserve_facts_must_match(verifier, key, value):
    md = reserve()
    c = E.classify(md, results(md, LIC + ("runner_token",), override={(verifier, key): value}),
                   fence=FENCE, config=CONFIG)
    assert_closed(c)


def test_verification_bound_to_other_metadata_is_rejected():
    md = captured()
    edited = copy.deepcopy(md)
    edited["span"]["start"] = "2026-07-02"
    c = E.classify(edited, results(edited, FWD, subject=E.subject_digest(md)), fence=FENCE, config=CONFIG)
    assert_closed(c)
    assert "integrity" in c.problems[0]


@pytest.mark.parametrize("names", [FWD[:-2] + FWD[-1:], FWD[1:], FWD + ("runner_token",), FWD + ("batch_freeze",),
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


def test_attempt_identity_needs_attempt_binding():
    md = captured(attempt_id=H("attempt"))
    assert_closed(run(md, FWD0))
    c = run(md, FWD)
    assert c.eligibility == E.E_FORWARD and c.identity.attempt_id == H("attempt") and c.identity.window_verified
    c = E.classify(md, results(md, FWD, override={("attempt_binding", "window_id"): "w9"}),
                   fence=FENCE, config=CONFIG)
    assert_closed(c)
    assert_closed(run(captured(attempt_id="not-a-hash"), FWD))


def test_forward_capture_without_attempt_binding_is_descriptive_only():
    md = captured()
    del md["attempt_id"]
    c = run(md, FWD0)
    assert c.provenance == E.CAPTURED_FORWARD and c.genuine_capture and not c.identity.window_verified
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0
    assert any("attempt binding" in b for b in c.blockers)


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
    c = run(reserve(), LIC + ("runner_token",))
    assert (c.role, c.authorization, c.eligibility) == (roles.RESERVE, E.AUTH_RESERVE, E.E_RESERVE)
    assert c.weight_ceiling == evidential_weight("blind", "reserve", True, False) == 1
    assert any("never independent forward confirmation" in b for b in c.blockers)
    assert_no_grant(c)


@pytest.mark.parametrize("change,avail", [({"spec": spec("adaptive")}, "release_dates"),
                                          ({"designated": False}, "release_dates"),
                                          ({}, "daily_lag"), ({}, "conservative")])
def test_reserve_candidate_requirements(change, avail):
    md = historical("licensed", start="2021-01-04", end="2023-12-29", avail=avail, designated=True)
    md.update(change)
    names = LIC + (("runner_token",) if md["designated"] else ())
    c = run(md, names)
    assert c.provenance == E.HISTORICAL_LICENSED
    assert c.eligibility in (E.E_DESCRIPTIVE, E.E_NONE) and c.weight_ceiling == 0


def test_reserve_disabled_in_config_authorises_nothing():
    c = run(reserve(), LIC + ("runner_token",), config={"reserve": {"enabled": False}})
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
        days.add(_bday(start, -k))          # before the reserve starts
        days.add(_bday(end, -k))            # before the reserve ends
    return sorted(days)


@pytest.mark.parametrize("h", [0, 5, 20])
def test_holding_period_embargo_matches_role_of_at_every_edge(h):
    for day in _edge_days(h):
        md = historical("licensed", start=day.isoformat(), end=day.isoformat(), spec=spec(holding=h),
                        designated=False)
        expected = roles.role_of(day, "fx_daily", BOUND_FENCE, date(2026, 6, 1), h)
        c = run(md, LIC, fence=BOUND_FENCE)
        assert c.role == expected, (h, day)
        if expected == roles.EMBARGO:
            assert c.eligibility == E.E_NONE and c.weight_ceiling == 0


@pytest.mark.parametrize("h", [0, 5, 20])
def test_holding_period_designated_reserve_edges(h):
    end = date(2020, 11, 30)
    for k in range(0, 25):
        day = _bday(end, -k)
        md = historical("licensed", start=day.isoformat(), end=day.isoformat(), spec=spec(holding=h),
                        designated=True)
        c = run(md, LIC + ("runner_token",), fence=BOUND_FENCE)
        embargoed = roles.role_of(day, "fx_daily", BOUND_FENCE, date(2026, 6, 1), h) == roles.EMBARGO
        if embargoed:
            assert_closed(c)                # 'designated' outside the reserve is contradictory
        else:
            assert c.eligibility == E.E_RESERVE and c.weight_ceiling == 1
        assert embargoed == (k < h + 1), (h, k)


def test_regression_holding_zero_no_longer_assumed():
    # 10 business days before the reserve ends: reserve for a 0-period spec, embargo for a 20-period spec.
    day = _bday(date(2024, 12, 31), -10).isoformat()
    md0 = reserve(span={"start": "2021-01-04", "end": day}, spec=spec(holding=0))
    md20 = reserve(span={"start": "2021-01-04", "end": day}, spec=spec(holding=20))
    assert run(md0, LIC + ("runner_token",)).eligibility == E.E_RESERVE
    c = run(md20, LIC + ("runner_token",))
    assert_closed(c)
    assert "several roles" in c.problems[0]


@pytest.mark.parametrize("bad", [None, -1, True, 1.0, "5", 10**9, [5]])
def test_unknown_or_malformed_holding_fails_closed(bad):
    md = captured()
    md["spec"]["holding_periods"] = bad
    assert_closed(run(md, FWD))


def test_missing_holding_fails_closed():
    md = captured()
    del md["spec"]["holding_periods"]
    assert_closed(run(md, FWD))


def test_contradictory_holding_fails_closed():
    md = reserve(spec=spec(holding=0))
    c = E.classify(md, results(md, LIC + ("runner_token",), override={("spec_registry", "holding_periods"): 20}),
                   fence=FENCE, config=CONFIG)
    assert_closed(c)
    assert "holding period" in c.problems[0]


# ---------------------------------------------------------------- M2: malformed config, fence, protocol hash

BAD_CONFIGS = [{"reserve": True}, {"reserve": None}, {"reserve": []}, {"reserve": "on"},
               {"reserve": {"enabled": "yes"}}, {"reserve": {"enabled": 1}}, {"claims": True},
               {"claims": []}, {"claims": {"enabled": "true"}}, {"claims": {"enabled": None}},
               "config", 5, [], ["reserve"], True]


@pytest.mark.parametrize("cfg", BAD_CONFIGS)
def test_malformed_config_fails_closed(cfg):
    for md, names in ((captured(), FWD), (reserve(), LIC + ("runner_token",)), (synthetic(), SYN)):
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
    for make, names in ((captured, FWD), (reserve, LIC + ("runner_token",)), (synthetic, SYN)):
        original = make()
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
            if md != original:
                # facts were stated about the original: any effective change must not survive
                assert c.provenance == E.UNVERIFIED or c.eligibility in (E.E_NONE, E.E_INFRA, E.E_DESCRIPTIVE) \
                    or c.identity == run(original, names).identity


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
    assert_closed(run(md, PUB + ("batch_freeze",)))


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
    assert_closed(run(md, FWD))


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
                                   {"holding_periods": 0}])
def test_unknown_fields_fail_closed(extra):
    md = historical()
    md.update(extra)
    assert_closed(run(md, PUB))


def test_designated_outside_reserve_is_forged():
    assert_closed(run(captured(designated=True), FWD + ("runner_token",)))


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
    lambda m: m.pop("schema"), lambda m: m.update(schema="manhattan.evidence/1"), lambda m: m.pop("spec"),
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
        kw["attempt_id"] = attempt
    return run(captured(start=start, end=end, window={"id": window}, **kw), FWD)


def test_combine_disjoint_parts_of_one_spec_keeps_every_part():
    a, b = _part("2026-07-01", "2026-07-31", "w1"), _part("2026-08-03", "2026-08-31", "w2")
    c = E.combine([a, b])
    assert c.eligibility == E.E_FORWARD and c.parts == (a, b) and c.subjects == (a.subject, b.subject)
    assert [p.provenance for p in c.parts] == [E.CAPTURED_FORWARD] * 2
    assert_no_grant(c)


def test_combine_rejects_duplicates():
    a = _part("2026-07-01", "2026-07-31", "w1")
    assert_closed(E.combine([a, a]))
    assert_closed(E.combine([a, _part("2026-08-03", "2026-08-31", "w1")]))             # same window
    x, y = _part("2026-07-01", "2026-07-31", "w1", H("a")), _part("2026-08-03", "2026-08-31", "w2", H("a"))
    assert_closed(E.combine([x, y]))                                                   # same attempt


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
    md = historical(start="2010-01-04", end="2014-12-31", window={"id": "w2"}, domain="rates")
    b = run(md, PUB)
    assert b.provenance == E.HISTORICAL_PUBLIC
    assert_closed(E.combine([a, b]))


def test_combine_attempt_identity_all_or_none():
    a = _part("2026-07-01", "2026-07-31", "w1", H("a1"))
    b = _part("2026-08-03", "2026-08-31", "w2", H("a2"))
    assert E.combine([a, b]).eligibility == E.E_FORWARD
    md = captured(start="2026-08-03", end="2026-08-31", window={"id": "w2"})
    del md["attempt_id"]
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
    assert c.parts[0].weight_ceiling == 1                     # parts keep their own classification


# ---------------------------------------------------------------- weight and purity

CASES = [
    lambda: run(synthetic(), SYN), lambda: run(historical(), PUB), lambda: run(historical("licensed"), LIC),
    lambda: run(reserve(), LIC + ("runner_token",)), lambda: run(captured(), FWD),
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
    assert mods <= {"__future__", "hashlib", "json", "re", "dataclasses", "datetime", "typing", "numpy",
                    "manhattan", "manhattan.availability", "manhattan.ledger", "manhattan.ops"}, mods
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls & {"open", "exec", "eval", "__import__"}


def test_classification_is_deterministic():
    md = captured()
    assert run(md, FWD) == run(copy.deepcopy(md), FWD)
