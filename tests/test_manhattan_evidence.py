"""Evidence classification (manhattan/evidence.py). Synthetic fixtures only: no market data is read."""
import copy
import hashlib
import inspect
from datetime import date

import pytest

from manhattan import evidence as E, roles
from manhattan.ledger import evidential_weight

FENCE = roles.Fence(exploration_end=date(2019, 12, 31),
                    reserve={"fx_daily": (date(2020, 3, 2), date(2024, 12, 31))}, enabled=True)
FENCE_OFF = roles.Fence(exploration_end=date(2019, 12, 31), reserve={}, enabled=False)
CONFIG = {"reserve": {"enabled": True}, "claims": {"enabled": False}}
H = lambda s: hashlib.sha256(s.encode()).hexdigest()


def contract(name="src", kind="daily_lag"):
    c = {"name": name, "frequency": "daily", "period_label": "observation_date",
         "availability": {"kind": kind, "reference": "synthetic fixture", "day_mapping": "close"}}
    if kind == "daily_lag":
        c["publication_lag_days"] = 1
    if kind == "conservative":
        c["availability"].update(assumption="a", owner_approval="b", release_history_unavailable="c")
    return c


def synthetic(**kw):
    md = {"schema": E.SCHEMA, "source": {"id": "src", "kind": "synthetic", "publication_contract": contract()},
          "domain": "fx_daily", "span": {"start": "2010-01-04", "end": "2010-12-31"},
          "vintage": {"kind": "generated", "id": H("gen"), "as_of": "2010-12-31"}, "designated": False}
    md.update(kw)
    return md


def historical(kind="public", start="2005-01-03", end="2019-12-31", avail="release_dates", **kw):
    md = {"schema": E.SCHEMA, "source": {"id": "src", "kind": kind, "publication_contract": contract(kind=avail)},
          "domain": "fx_daily", "span": {"start": start, "end": end},
          "vintage": {"kind": "snapshot", "id": H("snap"), "as_of": "2026-11-01"}, "designated": False}
    md.update(kw)
    return md


def spec(channel="blind", freeze="2026-06-01"):
    return {"spec_hash": H("spec"), "channel": channel, "freeze": freeze}


def captured(start="2026-07-01", end="2026-10-30", backfill=0, late=0, monitoring="2026-06-15", **kw):
    md = {"schema": E.SCHEMA, "source": {"id": "src", "kind": "public", "publication_contract": contract()},
          "domain": "fx_daily", "span": {"start": start, "end": end},
          "vintage": {"kind": "first_seen_capture", "id": H("cap"), "as_of": "2026-11-01"},
          "capture": {"capture_id": H("cap"), "schema_version": 2, "monitoring_start": monitoring,
                      "first_retrieved_utc": monitoring + "T22:30:00+00:00",
                      "reconstructed": {"backfill": backfill, "late": late}},
          "spec": spec(), "designated": False}
    md.update(kw)
    return md


def bound(md, *names):
    d = E.subject_digest(md)
    return {n: d for n in names}


ALL = tuple(E.VERIFIERS)


def run(md, names=ALL, fence=FENCE, config=CONFIG, **kw):
    return E.classify(md, bound(md, *names), fence=fence, config=config, **kw)


def assert_closed(c):
    assert c.provenance == E.UNVERIFIED and c.eligibility == E.E_NONE and c.weight_ceiling == 0
    assert c.problems
    assert_no_grant(c)


def assert_no_grant(c):
    assert c.forward_elond_eligible is False and c.screening_eligible is False and c.promotion_authorized is False
    assert c.blockers


# ---------------------------------------------------------------- legitimate classification

def test_synthetic_validates_infrastructure_only():
    c = run(synthetic(), ("synthetic_generator",))
    assert (c.provenance, c.availability, c.eligibility, c.weight_ceiling) == (
        E.SYNTHETIC, E.AVAIL_GENERATED, E.E_INFRA, 0)
    assert c.role == roles.EXPLORATION
    assert any("never market performance" in b for b in c.blockers)
    assert_no_grant(c)


def test_synthetic_on_forward_dates_is_still_infrastructure_only():
    md = synthetic(span={"start": "2026-07-01", "end": "2026-10-30"},
                   vintage={"kind": "generated", "id": H("g"), "as_of": "2026-10-30"}, spec=spec())
    c = run(md, ("synthetic_generator", "batch_freeze"))
    assert c.role == roles.FORWARD and c.eligibility == E.E_INFRA and c.weight_ceiling == 0


def test_historical_public_exploration_is_descriptive():
    c = run(historical(), ("publication_contract", "public_archive"))
    assert (c.provenance, c.licensed, c.role, c.authorization, c.eligibility, c.weight_ceiling) == (
        E.HISTORICAL_PUBLIC, False, roles.EXPLORATION, E.AUTH_OPEN, E.E_DESCRIPTIVE, 0)
    assert c.availability == E.AVAIL_PER_VINTAGE and not c.reconstruction


def test_historical_licensed_is_high_quality_but_not_forward_evidence():
    md = historical("licensed", start="2026-07-01", end="2026-10-30", spec=spec())
    c = run(md, ("publication_contract", "licensed_snapshot", "batch_freeze"))
    assert c.provenance == E.HISTORICAL_LICENSED and c.licensed and c.role == roles.FORWARD
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0 and not c.genuine_capture
    assert any("not captured forward evidence" in b for b in c.blockers)


def test_licensed_designated_reserve_is_a_screening_candidate_only():
    md = historical("licensed", start="2021-01-04", end="2023-12-29", spec=spec(), designated=True)
    c = run(md, ("publication_contract", "licensed_snapshot", "runner_token"))
    assert (c.role, c.authorization, c.eligibility) == (roles.RESERVE, E.AUTH_RESERVE, E.E_RESERVE)
    assert c.weight_ceiling == evidential_weight("blind", "reserve", True, False) == 1
    assert any("never independent forward confirmation" in b for b in c.blockers)
    assert_no_grant(c)


@pytest.mark.parametrize("change", [
    {"spec": spec("adaptive")}, {"designated": False}, {"avail": "daily_lag"}, {"avail": "conservative"}])
def test_reserve_candidate_requirements(change):
    change = dict(change)
    avail = change.pop("avail", "release_dates")
    md = historical("licensed", start="2021-01-04", end="2023-12-29", avail=avail,
                    **{"spec": spec(), "designated": True, **change})
    c = run(md)
    assert c.eligibility in (E.E_DESCRIPTIVE, E.E_NONE) and c.weight_ceiling == 0


def test_reserve_disabled_in_config_authorises_nothing():
    md = historical("licensed", start="2021-01-04", end="2023-12-29", spec=spec(), designated=True)
    c = run(md, config={"reserve": {"enabled": False}})
    assert c.authorization == E.AUTH_NONE and c.eligibility == E.E_NONE and c.weight_ceiling == 0


def test_genuine_capture_is_forward_candidate_but_never_elond_eligible():
    c = run(captured(), ("publication_contract", "capture_replay", "store_anchor", "batch_freeze"))
    assert c.genuine_capture and c.provenance == E.CAPTURED_FORWARD
    assert (c.role, c.authorization, c.eligibility) == (roles.FORWARD, E.AUTH_FREEZE, E.E_FORWARD)
    assert c.weight_ceiling == 1
    for gate in E.UNIMPLEMENTED_GATES:
        assert gate in c.blockers
    assert any("necessary, not sufficient" in b for b in c.blockers)
    assert "promotion disabled: no_adopted_protocol" in c.blockers
    assert_no_grant(c)


def test_capture_with_promotion_config_enabled_still_grants_nothing():
    cfg = {"reserve": {"enabled": True}, "claims": {"enabled": True}}
    c = run(captured(), config=cfg, protocol_hash=H("protocol"))
    assert c.eligibility == E.E_FORWARD
    assert_no_grant(c)


def test_licensed_captured_forward_keeps_licence_flag():
    md = captured()
    md["source"]["kind"] = "licensed"
    c = run(md)
    assert c.provenance == E.CAPTURED_FORWARD and c.licensed and c.eligibility == E.E_FORWARD


# ---------------------------------------------------------------- reconstructed / backfilled

@pytest.mark.parametrize("kw,reason", [({"backfill": 3}, E.BACKFILLED), ({"late": 1}, E.LATE)])
def test_reconstructed_capture_is_explicit_and_weightless(kw, reason):
    c = run(captured(**kw))
    assert c.provenance == E.CAPTURED_FORWARD and reason in c.reconstruction and not c.genuine_capture
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0
    assert evidential_weight("blind", "forward", False, True) == 0


def test_conservative_availability_capture_is_reconstructed():
    md = captured()
    md["source"]["publication_contract"] = contract(kind="conservative")
    c = run(md)
    assert E.CONSERVATIVE in c.reconstruction and c.availability == E.AVAIL_CONSERVATIVE
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0


def test_backfilled_history_masquerading_as_captured_forward():
    # the span starts before monitoring began, yet no backfill is reported
    c = run(captured(start="2026-06-02", monitoring="2026-09-01"))
    assert_closed(c)
    assert "posing as captured" in c.problems[0]


def test_backfill_reported_honestly_is_flagged_not_rejected():
    c = run(captured(start="2026-06-02", monitoring="2026-09-01", backfill=60))
    assert E.BACKFILLED in c.reconstruction and c.weight_ceiling == 0


def test_snapshot_vintage_with_capture_block_fails_closed():
    md = captured()
    md["vintage"]["kind"] = "snapshot"
    assert_closed(run(md))


def test_capture_block_without_capture_vintage_kind():
    md = captured()
    del md["capture"]
    c = run(md)
    assert_closed(c)


def test_recent_dates_alone_never_make_captured_forward():
    md = historical("public", start="2026-07-01", end="2026-10-30", spec=spec())
    c = run(md)
    assert c.provenance == E.HISTORICAL_PUBLIC and c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0


# ---------------------------------------------------------------- adversarial metadata

def test_missing_source_definition():
    md = captured()
    del md["source"]["publication_contract"]
    assert_closed(run(md))


@pytest.mark.parametrize("mutate", [
    lambda c: c.update(frequency="monthly"),                      # daily_lag on monthly data
    lambda c: c["availability"].update(kind="guess"),
    lambda c: c["availability"].update(reference=""),
    lambda c: c.update(publication_lag_days=-1),
    lambda c: c.update(name="other"),                             # contract for a different source
    lambda c: c.pop("period_label"),
])
def test_invalid_publication_contract(mutate):
    md = captured()
    mutate(md["source"]["publication_contract"])
    assert_closed(run(md))


@pytest.mark.parametrize("mutate", [
    lambda m: m["span"].update(start="2026-11-02"),               # span ends before it starts
    lambda m: m["span"].update(end="2026-11-20"),                 # vintage as_of precedes the span end
    lambda m: m["capture"].update(first_retrieved_utc="2026-01-01T00:00:00+00:00"),  # vs monitoring start
    lambda m: m["capture"].update(monitoring_start="2026-11-05",
                                  first_retrieved_utc="2026-11-05T00:00:00+00:00"),  # after the vintage
    lambda m: m["capture"].update(first_retrieved_utc="2026-06-15T22:30:00"),        # no time zone
    lambda m: m["span"].update(start="2026-02-30"),
    lambda m: m["span"].update(start=20260701),
    lambda m: m["spec"].update(freeze="2026-08-01"),              # freeze inside the span: mixed roles
])
def test_inconsistent_dates(mutate):
    md = captured()
    mutate(md)
    assert_closed(run(md))


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
    assert_closed(run(md))


@pytest.mark.parametrize("label", [roles.FORWARD, roles.RESERVE, "confirmatory"])
def test_forged_role_label(label):
    md = historical("licensed", claimed_role=label)               # exploration dates
    assert_closed(run(md))


def test_true_role_label_is_accepted_but_changes_nothing():
    a, b = run(historical()), run(historical(claimed_role=roles.EXPLORATION))
    assert (a.provenance, a.eligibility, a.weight_ceiling) == (b.provenance, b.eligibility, b.weight_ceiling)


def test_forged_provenance_label():
    assert_closed(run(historical(claimed_provenance=E.CAPTURED_FORWARD)))


@pytest.mark.parametrize("extra", [{"evidential_weight": 1}, {"eligible": True}, {"filename": "captured_forward.csv"},
                                   {"provenance": E.CAPTURED_FORWARD}, {"tier": "formally_supported"}])
def test_unknown_fields_fail_closed(extra):
    md = historical()
    md.update(extra)
    assert_closed(run(md))


def test_designated_outside_reserve_is_forged():
    assert_closed(run(captured(designated=True)))


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
    assert_closed(run(md))


@pytest.mark.parametrize("drop", [
    lambda m: m.pop("source"), lambda m: m.pop("span"), lambda m: m.pop("vintage"), lambda m: m.pop("designated"),
    lambda m: m.pop("schema"), lambda m: m.update(schema="manhattan.evidence/0"),
    lambda m: m["capture"].pop("reconstructed"), lambda m: m["capture"]["reconstructed"].pop("late"),
    lambda m: m["capture"]["reconstructed"].update(late=-1), lambda m: m["spec"].pop("freeze"),
    lambda m: m["source"].update(kind="vendor"), lambda m: m.update(domain=""),
])
def test_incomplete_metadata(drop):
    md = captured()
    drop(md)
    assert_closed(run(md))


@pytest.mark.parametrize("bad", [None, [], "captured_forward", 3, {"schema": E.SCHEMA, "x": float("nan")}])
def test_non_metadata_fails_closed(bad):
    assert_closed(E.classify(bad, {}, fence=FENCE, config=CONFIG))


# ---------------------------------------------------------------- verification binding

def test_missing_verification_fails_closed():
    c = run(captured(), ("publication_contract", "capture_replay", "batch_freeze"))   # no store anchor
    assert_closed(c)


def test_forward_role_needs_verified_freeze():
    assert_closed(run(captured(), ("publication_contract", "capture_replay", "store_anchor")))


def test_verification_bound_to_other_metadata_is_rejected():
    md = captured()
    v = bound(md, *ALL)
    md2 = copy.deepcopy(md)
    md2["capture"]["reconstructed"]["late"] = 0
    md2["span"]["start"] = "2026-07-02"                            # edited after verification
    assert_closed(E.classify(md2, v, fence=FENCE, config=CONFIG))


def test_unknown_verifier_and_no_verifications():
    md = captured()
    v = bound(md, *ALL)
    v["trust_me"] = E.subject_digest(md)
    assert_closed(E.classify(md, v, fence=FENCE, config=CONFIG))
    assert_closed(E.classify(md, None, fence=FENCE, config=CONFIG))
    assert_closed(E.classify(md, {}, fence=FENCE, config=CONFIG))


def test_reserve_designation_needs_runner_token():
    md = historical("licensed", start="2021-01-04", end="2023-12-29", spec=spec(), designated=True)
    assert_closed(run(md, ("publication_contract", "licensed_snapshot")))


def test_embargo_and_disabled_reserve():
    c = run(historical(start="2020-01-02", end="2020-01-10"))      # between exploration end and reserve
    assert c.role == roles.EMBARGO and c.eligibility == E.E_NONE and c.weight_ceiling == 0
    c = run(historical("licensed", start="2021-01-04", end="2021-02-26"), fence=roles.Fence(
        exploration_end=date(2019, 12, 31), reserve=FENCE.reserve, enabled=False))
    assert c.role == roles.EMBARGO and c.eligibility == E.E_NONE


def test_span_across_fence_fails_closed():
    assert_closed(run(historical(start="2019-06-03", end="2021-06-30")))


# ---------------------------------------------------------------- mixed provenance and weight

def test_mixed_provenance_fails_closed():
    a = run(captured())
    b = run(historical("licensed", start="2026-07-01", end="2026-10-30", spec=spec()))
    assert_closed(E.combine([a, b]))
    assert_closed(E.combine([a, run(synthetic())]))
    assert_closed(E.combine([a, E.classify({}, {}, fence=FENCE)]))
    assert_closed(E.combine([]))


def test_combine_takes_the_weakest_part():
    good, recon = run(captured()), run(captured(late=2))
    c = E.combine([good, recon])
    assert c.provenance == E.CAPTURED_FORWARD and E.LATE in c.reconstruction
    assert c.eligibility == E.E_DESCRIPTIVE and c.weight_ceiling == 0
    assert E.combine([good, good]).eligibility == E.E_FORWARD
    assert_no_grant(E.combine([good, good]))


CASES = [
    lambda: run(synthetic()), lambda: run(historical()), lambda: run(historical("licensed")),
    lambda: run(historical("licensed", start="2021-01-04", end="2023-12-29", spec=spec(), designated=True)),
    lambda: run(captured()), lambda: run(captured(late=1)), lambda: run(captured(), ()),
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
        recon = bool(c.reconstruction)
        assert c.weight_ceiling == evidential_weight("blind", c.role, c.role == "reserve", recon)
    else:
        assert c.weight_ceiling == 0


def test_module_is_pure():
    import ast
    tree = ast.parse(inspect.getsource(E))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert mods <= {"__future__", "hashlib", "json", "re", "dataclasses", "datetime", "typing", "numpy",
                    "manhattan", "manhattan.availability", "manhattan.ledger", "manhattan.ops"}, mods
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls & {"open", "exec", "eval", "__import__"}


def test_classification_is_deterministic():
    md = captured()
    assert run(md) == run(copy.deepcopy(md))
