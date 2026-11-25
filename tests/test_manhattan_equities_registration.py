"""Hypothesis first (issue #102 review): a draft catalogue family never becomes an executable experiment without a
pre-registered, immutable specification verified by ``manhattan.freeze.verify_frozen``.

Adversarial regression tests:

- missing registrations;
- modified specifications, families, files and handles;
- incomplete specifications;
- holdout leakage;
- cross-track double counting;
- attempt-accounting identity;
- dormancy.

Every batch here is a **test fixture** written to a temporary directory, "signed" by a fixture key and "timestamped"
by a fixture proof through the test-only seam ``tests/manhattan_freeze_seam.py`` (``verify_frozen`` itself takes no
substitutable check, and its production pin is empty: S17 C2). Every holdout look is recorded in a fixture ledger
in a temporary directory under a synthetic fence. Nothing is pre-registered, and no file in the repository is written.
"""
from __future__ import annotations

import ast
import dataclasses
import itertools
import json
from datetime import date
from pathlib import Path

import manhattan_freeze_seam as seam
import pytest

from manhattan import freeze as FZ
from manhattan import ledger as L
from manhattan import roles
from manhattan import spec as S
from manhattan.engine import evaluate
from manhattan.equities import catalogue as C
from manhattan.equities import registration as R
from manhattan.equities import sector_synthetic as SS
from manhattan.equities import track_compare as TC
from manhattan.equities.costs import EquityCostModel
from manhattan.equities.errors import EquityDataError

ROOT = Path(__file__).resolve().parents[1]
NT, TE = "non_technology_equities", "technology_equities"
CODE = "c" * 40
COSTS = dict(half_spread=0.0005, commission=0.0001, impact=0.1, short_financing=0.0, long_financing=0.0,
             recall_cost=0.0, reference="test fixture, not a measurement")
WINDOWS = dict(selection_end=date(2006, 12, 29), holdout_start=date(2007, 1, 2), holdout_end=date(2008, 12, 31))
REJECT = [{"metric": "excess_sharpe", "op": "<=", "value": 0.0}]
_BATCHES = itertools.count(910)          # a fresh batch, and so a fresh registration, per test
HOLDOUT_WINDOW = "synthetic-equities-holdout"
# a synthetic fence: the reserve is enabled and its windows cover the synthetic holdout (test fixture, not config)
FENCE = roles.Fence(exploration_end=date(2006, 12, 29), enabled=True,
                    reserve={f"equities:{NT}": (date(2007, 1, 1), date(2009, 6, 30)),
                             f"equities:{TE}": (date(2007, 1, 1), date(2009, 6, 30))})
CV = {"commit": "c" * 40, "engine_sha256": "e" * 64}      # a fixture code identity


@pytest.fixture(autouse=True)
def fixture_trust():
    with seam.fixture_trust():
        yield


def ledger(tmp_path):
    return L.Ledger(tmp_path / "holdout-ledger.jsonl", writer="test fixture", protocol="0" * 64)


def holdout(world, exp, lock, cm, tmp_path, **kw):
    return R.run_holdout(world, exp, lock, cm, ledger=kw.pop("book", None) or ledger(tmp_path),
                         fence=kw.pop("fence", FENCE), code_version=CV, **kw)


@pytest.fixture(scope="module")
def cm():
    return EquityCostModel(**COSTS)


@pytest.fixture(scope="module")
def cats():
    return C.load(), C.load(C.NT_PATH)


def entry(cats, fid):
    te, nt = cats
    return next(f for f in te["families"] + nt["families"] if f["id"] == fid)


def draft(cats, cm, fid="NT-M01", programme=NT, batch="AB-0901", **over):
    kw = dict(construction="trailing total return over the lookback, skipping the last month", lookbacks=[63, 126],
              skip=21, top_fraction=1 / 3, cost_model=cm, lag=1, rejection_criteria=REJECT, batch=batch, **WINDOWS)
    kw.update(over)
    return R.experiment_spec(entry(cats, fid), programme=programme, **kw)


def freeze_fixture(tmp_path, cats, pairs, number=901, code=CODE, ots=True, signer=seam.FIXTURE_OWNER):
    """A batch frozen in a temporary directory (test fixture). ``pairs``: [(catalogue entry id, programme, spec)]."""
    fams, hyps = [], []
    for fid, prog, hyp in pairs:
        fam = C.family_draft(entry(cats, fid), programme=prog)
        if fam not in fams:
            fams.append(fam)
        hyps.append(hyp)
    b = FZ.prepare(number, fams, hyps, channel="blind", template_hash="0" * 64, generator_model="test fixture",
                   protocol_hash="0" * 64, fence={}, code_version=code,
                   critic_records=["test fixture critic record, not a review"],
                   reserve_window_ids={f"equities:{NT}": HOLDOUT_WINDOW, f"equities:{TE}": HOLDOUT_WINDOW})
    FZ.write(b, tmp_path)
    seam.freeze_fixture(tmp_path, b.number, signer=signer, ots=ots)
    return b


def admit(cats, hyp, b, tmp_path, fid="NT-M01", programme=NT, **kw):
    args = dict(programme=programme, batch_dir=tmp_path, batch_number=b.number, manifest_hash=b.manifest_hash,
                code_version=CODE)
    args.update(kw)
    return R.admit(entry(cats, fid), hyp, **args)


@pytest.fixture()
def admitted(tmp_path, cats, cm):
    n = next(_BATCHES)
    hyp = draft(cats, cm, batch=f"AB-{n:04d}")
    b = freeze_fixture(tmp_path, cats, [("NT-M01", NT, hyp)], number=n)
    return hyp, b, admit(cats, hyp, b, tmp_path)


# ------------------------------------------------------------------------------------------ draft is not experiment

def test_a_draft_family_never_becomes_an_executable_experiment(cats, cm, tmp_path):
    e = entry(cats, "NT-M01")
    assert C.family_draft(e, programme=NT)["status"] == "draft"
    hyp = draft(cats, cm)                                       # a spec drafted but never frozen
    world = SS.sector_world()
    for bad in (e, C.family_draft(e, programme=NT), hyp):
        with pytest.raises(R.RegistrationError):
            R.run_selection(world, bad, cm)
    forged = R.ExperimentHandle(S.spec_hash(hyp), "f" * 64, S.canonical_bytes(hyp), NT, "NT-M01", "AB-0901",
                                "m" * 64, ((63, "a" * 64, "b" * 64),))
    with pytest.raises(R.RegistrationError, match="not an admitted experiment"):
        R.run_selection(world, forged, cm)
    with pytest.raises(R.RegistrationError, match="no verified freeze"):
        R.admit(e, hyp, programme=NT, batch_dir=tmp_path, batch_number=901, manifest_hash="0" * 64,
                code_version=CODE)


# ------------------------------------------------------------------------------------------- missing registrations

def test_missing_or_unverifiable_registrations_are_refused(tmp_path, cats, cm):
    hyp = draft(cats, cm)
    other = draft(cats, cm, lookbacks=[63, 252])               # a different experiment of the same family
    b = freeze_fixture(tmp_path, cats, [("NT-M01", NT, other)])
    with pytest.raises(R.RegistrationError, match="this experiment spec is not in the frozen batch"):
        admit(cats, hyp, b, tmp_path)                           # the batch froze something else
    with seam.production_trust(), pytest.raises(R.RegistrationError, match="ALLOWED_FREEZE_SIGNERS is empty"):
        admit(cats, other, b, tmp_path)                         # the production check: no owner key is pinned
    with seam.trust(signers={seam.FIXTURE_OTHER}), pytest.raises(R.RegistrationError, match="not a pinned owner"):
        admit(cats, other, b, tmp_path)                         # signed, but by a key that is not pinned
    t3 = tmp_path / "unsigned"
    b3 = freeze_fixture(t3, cats, [("NT-M01", NT, other)], signer=None)
    with pytest.raises(R.RegistrationError, match="not signed"):
        admit(cats, other, b3, t3)
    with pytest.raises(R.RegistrationError, match="does not match the hash"):
        admit(cats, other, b, tmp_path, manifest_hash="ab" * 32)
    t2 = tmp_path / "no_ots"
    b2 = freeze_fixture(t2, cats, [("NT-M01", NT, hyp)], number=902, ots=False)
    with pytest.raises(R.RegistrationError, match="timestamp"):
        admit(cats, hyp, b2, t2)


# ------------------------------------------------------------------------------------------ modified specifications

@pytest.mark.parametrize("mutate", [
    lambda h: h["grid"].update(lookback=[63, 126, 252]),                     # a variant added after looking
    lambda h: h["costs"].update(half_spread=0.0001),                          # cheaper costs after registration
    lambda h: h["windows"].update(holdout_start="2007-06-01"),                # moved holdout
    lambda h: h.update(rejection_criteria=[{"metric": "excess_sharpe", "op": "<=", "value": -5.0}]),
    lambda h: h["signal"].update(skip=0),
    lambda h: h["execution"].update(lag=2),
])
def test_a_specification_modified_after_registration_is_refused(admitted, cats, tmp_path, mutate):
    hyp, b, _ = admitted
    changed = json.loads(S.canonical_bytes(hyp))
    mutate(changed)
    with pytest.raises(R.RegistrationError, match="modified after registration"):
        admit(cats, changed, b, tmp_path)


def test_a_spec_file_edited_in_the_batch_is_refused(admitted, cats, tmp_path):
    hyp, b, _ = admitted
    f = next((tmp_path / b.id / "specs").glob(f"AH-{S.spec_hash(hyp)[:16]}.json"))
    f.write_bytes(f.read_bytes().replace(b'"lag":1', b'"lag":2'))
    with pytest.raises(R.RegistrationError, match="no verified freeze"):
        admit(cats, hyp, b, tmp_path)


def test_a_catalogue_family_edited_after_registration_is_refused(admitted, cats, tmp_path):
    hyp, b, _ = admitted
    edited = json.loads(json.dumps(entry(cats, "NT-M01")))
    edited["rationale"] += " Also, investors herd."
    with pytest.raises(R.RegistrationError, match="catalogue family, as drafted now"):
        R.admit(edited, hyp, programme=NT, batch_dir=tmp_path, batch_number=b.number, manifest_hash=b.manifest_hash,
                code_version=CODE)


def test_handles_cannot_be_copied_or_edited_and_runs_use_only_registered_terms(admitted, cats, cm, tmp_path):
    hyp, b, exp = admitted
    world = SS.sector_world()
    with pytest.raises(R.RegistrationError, match="not an admitted"):
        R.run_selection(world, dataclasses.replace(exp, track=TE), cm)        # an edited copy loses the seal
    with pytest.raises(R.RegistrationError, match="not an admitted"):
        R.run_selection(world, dataclasses.replace(exp, seal="0" * 64), cm)
    with pytest.raises(R.RegistrationError, match="cost model differs"):
        R.run_selection(world, exp, EquityCostModel(**{**COSTS, "impact": 0.0}))
    with pytest.raises(R.RegistrationError):                    # another engine identity: not the frozen executables
        admit(cats, hyp, b, tmp_path, code_version="d" * 40)
    with pytest.raises(R.RegistrationError):
        admit(cats, hyp, b, tmp_path, programme=TE)              # another track
    object.__setattr__(exp, "canonical", exp.canonical.replace(b'"lag":1', b'"lag":3'))
    with pytest.raises(R.RegistrationError):
        R.run_selection(world, exp, cm)


# ----------------------------------------------------------------------------------------- incomplete specifications

@pytest.mark.parametrize("over,expect", [
    (dict(lag=0), "lag"),
    (dict(rejection_criteria=[]), "rejection"),
    (dict(rejection_criteria=[{"metric": "sharpe", "op": "<", "value": 0}]), "rejection criteria"),
    (dict(selection_end=date(2007, 6, 29)), "windows"),                       # selection overlaps the holdout
    (dict(construction="  "), "construction"),
    (dict(lookbacks=[10]), "lookbacks"),
    (dict(data_sources=["security_master", "analyst_estimates_pit"]), "data kinds"),
    (dict(batch="unregistered"), "attempt accounting"),
])
def test_an_incomplete_or_inconsistent_specification_is_refused(cats, cm, over, expect):
    with pytest.raises(R.RegistrationError, match=expect):
        draft(cats, cm, **over)


@pytest.mark.parametrize("field", [f for f in R.REQUIRED if f not in ("schema",)])
def test_every_required_field_is_required(cats, cm, field):
    hyp = json.loads(S.canonical_bytes(draft(cats, cm)))
    hyp.pop(field, None)
    assert R.validate_spec(entry(cats, "NT-M01"), hyp, programme=NT)


def test_the_predicted_direction_and_mechanism_must_be_the_familys(cats, cm):
    hyp = json.loads(S.canonical_bytes(draft(cats, cm)))
    hyp["predicted_sign"] = "-"
    errs = R.validate_spec(entry(cats, "NT-M01"), hyp, programme=NT)
    assert any("predicted direction" in e for e in errs)
    with pytest.raises(R.RegistrationError):                    # a non-technology family drafted in the tech track
        R.experiment_spec(entry(cats, "NT-M01"), programme="combined_equities", construction="x", lookbacks=[63],
                          skip=21, top_fraction=0.3, cost_model=cm, lag=1, rejection_criteria=REJECT,
                          batch="AB-0901", **WINDOWS)


# ------------------------------------------------------------------------------------------------- holdout leakage

def test_selection_reads_nothing_after_its_cutoff(tmp_path, cats, cm):
    n = next(_BATCHES)
    hyp = draft(cats, cm, batch=f"AB-{n:04d}")
    b = freeze_fixture(tmp_path, cats, [("NT-M01", NT, hyp)], number=n)
    exp = admit(cats, hyp, b, tmp_path)
    plain = SS.sector_world()
    future_only = SS.sector_world(planted_momentum=0.004, planted_from=WINDOWS["holdout_start"])
    a, z = R.run_selection(plain, exp, cm), R.run_selection(future_only, exp, cm)
    assert (a.chosen_lookback, a.in_sample) == (z.chosen_lookback, z.in_sample)   # the holdout's effect is unseen
    assert "holdout" not in a.in_sample and a.variants_tried == 2
    v = holdout(future_only, exp, z, cm, tmp_path)             # ... and found only when the holdout is read
    assert v["excess_over_benchmark"]["sharpe"] > 1 and v["rejected"] is False
    assert v["holdout"]["start"] == "2007-01-02" and v["evidential_weight"] == 0


class _NothingAfter:
    """A price book that fails any read dated after ``cutoff`` (instrumentation for the leakage test)."""

    def __init__(self, book, cutoff):
        self._book, self._cutoff = book, cutoff

    def __getattr__(self, name):
        attr = getattr(self._book, name)
        if not callable(attr):
            return attr

        def guarded(*args, **kw):
            for v in list(args) + list(kw.values()):
                if isinstance(v, date) and v > self._cutoff:
                    raise AssertionError(f"{name} read {v}, after the selection cutoff {self._cutoff}")
            return attr(*args, **kw)
        return guarded


def test_selection_never_reads_a_price_dated_after_its_cutoff(admitted, cm):
    _, _, exp = admitted
    w = SS.sector_world()
    guarded = seam.mark_synthetic(dataclasses.replace(w, prices=_NothingAfter(w.prices, WINDOWS["selection_end"])),
                                  "selection reads nothing after its cutoff")
    lock = R.run_selection(guarded, exp, cm)                   # raises if anything after the cutoff is touched
    assert lock.in_sample == R.run_selection(w, exp, cm).in_sample


def test_the_holdout_needs_a_lock_and_is_read_once(admitted, cats, cm, tmp_path):
    hyp, b, exp = admitted
    world = SS.sector_world()
    forged = R.SelectionLock(exp.spec_hash, 126, 2, "{}")
    with pytest.raises(R.RegistrationError, match="selection lock"):
        holdout(world, exp, forged, cm, tmp_path)              # no lock was issued: the holdout stays untouched
    n = next(_BATCHES)
    other_hyp = draft(cats, cm, lookbacks=[63, 252], batch=f"AB-{n:04d}")
    t2 = tmp_path / "other"
    b2 = freeze_fixture(t2, cats, [("NT-M01", NT, other_hyp)], number=n)
    other = admit(cats, other_hyp, b2, t2)
    with pytest.raises(R.RegistrationError, match="selection lock"):
        holdout(world, exp, R.run_selection(world, other, cm), cm, tmp_path)   # another experiment's lock
    lock = R.run_selection(world, exp, cm)
    book = ledger(tmp_path)
    v = holdout(world, exp, lock, cm, tmp_path, book=book)
    assert v["criteria_met"] == ([REJECT[0]] if v["rejected"] else [])
    with pytest.raises(R.RegistrationError, match="one look"):
        holdout(world, exp, lock, cm, tmp_path, book=book)
    with pytest.raises(R.RegistrationError, match="one look"):
        holdout(world, exp, lock, cm, tmp_path)                  # a fresh Ledger object on the same file


# -------------------------------------------------------------------------------------- cross-track double counting

def test_cross_track_and_duplicate_registrations_are_never_double_counted(tmp_path, cats, cm):
    m_nt = draft(cats, cm, "NT-M01", NT, batch="AB-0904")
    with pytest.raises(R.RegistrationError, match="no executable signal implements family NT-L01"):
        draft(cats, cm, "NT-L01", NT, batch="AB-0904")          # the same experiment under another family (C10)
    m_te = draft(cats, cm, "TE-E01", TE, batch="AB-0904")       # the linked mechanism in the technology track
    b = freeze_fixture(tmp_path, cats, [("NT-M01", NT, m_nt), ("TE-E01", TE, m_te)], 904)
    a = admit(cats, m_nt, b, tmp_path, "NT-M01", NT)
    t = admit(cats, m_te, b, tmp_path, "TE-E01", TE)
    rep = R.count_registered([a, a, t], nontech_catalogue=cats[1])
    assert rep["by_track"] == {TE: 1, NT: 1} and rep["combined"] == 2
    reasons = [r["reason"] for r in rep["refused"]]
    assert any("duplicate registration" in r for r in reasons)
    assert rep["dependent_cross_track_groups"] == [{"mechanism": "XM-MOMENTUM", "families": ["NT-M01", "TE-E01"]}]
    assert rep["same_experiment_in_two_tracks"] == [{"families": ["NT-M01", "TE-E01"], "tracks": [NT, TE]}]
    assert rep["independent_confirmations"] == 0 and rep["denominator"] is None        # NT-8 / D-1 not decided


# ------------------------------------------------------------------------------------------ attempt accounting

def test_each_variant_has_a_pr86_attempt_identity(admitted):
    _, b, exp = admitted
    window = {"id": "synthetic-holdout", "start": "2007-01-02", "end": "2008-12-31", "frequency": "daily"}
    ids = [R.attempt_identity(exp, lb, data_hash="d" * 64, window=window, code_version=evaluate.code_version())
           for lb in (63, 126)]
    for x in ids:
        L.validate_attempt_identity(x)
        assert (x["role"], x["channel"], x["designated"], x["batch"]) == ("exploration", "blind", False, b.id)
    assert ids[0]["executable"] != ids[1]["executable"] and ids[0]["hypothesis"] == ids[1]["hypothesis"]
    with pytest.raises(R.RegistrationError, match="not a declared variant"):
        R.attempt_identity(exp, 252, data_hash="d" * 64, window=window, code_version=evaluate.code_version())


# ------------------------------------------------------------------------------------------------------ dormancy

def test_dormant_nothing_runs_on_a_world_that_is_not_a_synthetic_fixture(admitted, cm):
    _, _, exp = admitted
    unmarked = dataclasses.replace(SS.sector_world())           # same contents, not issued by a generator
    with pytest.raises(R.RegistrationError, match="synthetic"):
        R.run_selection(unmarked, exp, cm)
    with pytest.raises(EquityDataError, match="synthetic"):
        TC._compare(unmarked, TC.CompareConfig(is_end=date(2006, 12, 29)), cm)
    with pytest.raises(EquityDataError, match="synthetic"):
        TC.sector_volatility(unmarked, date(2004, 1, 2), date(2005, 1, 3))
    tree = ast.parse((ROOT / "manhattan/equities/registration.py").read_text(encoding="utf-8"))
    sets = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
            for t in n.targets if isinstance(t, ast.Name) and t.id == "EXECUTION_ON_REAL_DATA"]
    assert len(sets) == 1 and sets[0].value.value is False
