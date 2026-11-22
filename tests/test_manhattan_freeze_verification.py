"""PR-2 (S17 C1, C2, C10): genuine freeze verification and a persistent single-look equities holdout.

Acceptance tests P2-a to P2-h of ``docs/manhattan/audit/S17_NEXT_PRS.md`` (branch
``claude/manhattan-comprehensive-audit-i7a2ov``). Each fails on ``origin/main`` before this change and passes after.

- P2-a  the S17 self-certified batch (``b"not a proof"`` as the ``.ots``, an always-true signature) is refused;
- P2-b  a tag signed by a key that is not pinned is refused;
- P2-c  the fixture owner key plus a valid fixture proof is admitted (through the test-only seam only);
- P2-d  two separate OS processes call ``run_holdout`` on the same batch and ledger, one after the other: exactly one
        read, the second raises, the ledger shows one designated start. A **concurrent** race test is deferred until
        PR-1's ledger writer lock lands (the two-process guarantee for simultaneous writers rests on it);
- P2-e  a new handle, a new ``Ledger`` object, a module reload: the second look is still refused;
- P2-f  forged selection locks (lookback not in the grid, variant count disagreeing with the registration, a choice
        that is not the rule's) and forged handles are refused;
- P2-g  a 2023-01-03..2026-09-30 holdout with main's configuration is refused (reserve off, no windows);
- P2-h  ``track_compare.run_sleeve`` on a holdout window, outside the gate, is refused;
- C10   a family whose declared signal and sign no executable signal implements cannot be registered.

Synthetic only: every batch, signature, timestamp proof, fence and ledger is a fixture in a temporary directory.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

import manhattan_freeze_seam as seam
from manhattan import config as MC
from manhattan import freeze as FZ
from manhattan import ledger as L
from manhattan import roles
from manhattan.engine import evaluate
from manhattan.equities import catalogue as C
from manhattan.equities import registration as R
from manhattan.equities import sector_synthetic as SS
from manhattan.equities import synthetic as SY
from manhattan.equities import track_compare as TC
from manhattan.equities.costs import EquityCostModel
from manhattan.equities.errors import EquityDataError

ROOT = Path(__file__).resolve().parents[1]
NT = "non_technology_equities"
DOMAIN = f"equities:{NT}"
CODE = "c" * 40
CV = {"commit": "c" * 40, "engine_sha256": "e" * 64}          # a fixture code identity
COSTS = dict(half_spread=0.0005, commission=0.0001, impact=0.1, short_financing=0.0, long_financing=0.0,
             recall_cost=0.0, reference="synthetic")
WINDOWS = dict(selection_end=date(2006, 12, 29), holdout_start=date(2007, 1, 2), holdout_end=date(2008, 12, 31))
REJECT = [{"metric": "excess_sharpe", "op": "<=", "value": 0.0}]
HOLDOUT_WINDOW = "synthetic-equities-holdout"
FENCE = roles.Fence(exploration_end=date(2006, 12, 29), enabled=True, reserve={DOMAIN: (date(2007, 1, 1),
                                                                                     date(2009, 6, 30))})


@pytest.fixture(scope="module")
def cm():
    return EquityCostModel(**COSTS)


@pytest.fixture(scope="module")
def nt():
    return C.load(C.NT_PATH)


def _entry(nt, fid="NT-M01"):
    return next(f for f in nt["families"] if f["id"] == fid)


def _spec(nt, cm, number, fid="NT-M01", windows=WINDOWS, lookbacks=(63, 126)):
    return R.experiment_spec(_entry(nt, fid), programme=NT, construction="x", lookbacks=list(lookbacks), skip=21,
                             top_fraction=1 / 3, cost_model=cm, lag=1, rejection_criteria=REJECT,
                             batch=f"AB-{number:04d}", **windows)


def _batch(base: Path, nt, cm, number, *, windows=WINDOWS, designate=True):
    """The S17 reproduction's batch (AB-0777 shape), written but neither signed nor stamped."""
    hyp = _spec(nt, cm, number, windows=windows)
    b = FZ.prepare(number, [C.family_draft(_entry(nt), programme=NT)], [hyp], channel="blind",
                   template_hash="0" * 64, generator_model="agent", protocol_hash="0" * 64, fence={},
                   code_version=CODE, critic_records=["self-written"],
                   reserve_window_ids={DOMAIN: HOLDOUT_WINDOW} if designate else None)
    FZ.write(b, base)
    return hyp, b


def _admit(nt, hyp, b, base):
    return R.admit(_entry(nt), hyp, programme=NT, batch_dir=base, batch_number=b.number,
                   manifest_hash=b.manifest_hash, code_version=CODE)


def _ledger(path: Path):
    return L.Ledger(path, writer="test fixture", protocol="0" * 64)


def _starts(path: Path) -> list:
    return [r for r in L.read(path) if r["type"] == "evaluation_started"] if path.exists() else []


# ------------------------------------------------------------------------------------------------ P2-a

def test_p2a_the_checks_are_not_public_parameters():
    for fn in (FZ.verify_frozen, R.admit):
        params = inspect.signature(fn).parameters
        assert not {"tag_is_signed", "timestamp", "timestamp_verifier", "verifier", "trust"} & set(params), fn


def test_p2a_the_self_certified_batch_is_refused(tmp_path, nt, cm):
    hyp, b = _batch(tmp_path, nt, cm, 777)
    (tmp_path / b.id / FZ.TIMESTAMP_PROOF).write_bytes(b"not a proof")
    always = lambda t, r, *a: True        # noqa: E731  the S17 reproduction's "signature"
    with pytest.raises((FZ.FreezeError, TypeError)):
        FZ.verify_frozen(tmp_path, 777, tag_is_signed=always)
    with pytest.raises((R.RegistrationError, TypeError)):
        R.admit(_entry(nt), hyp, programme=NT, batch_dir=tmp_path, batch_number=777, manifest_hash=b.manifest_hash,
                code_version=CODE, tag_is_signed=always)
    with pytest.raises(FZ.FreezeError, match="ALLOWED_FREEZE_SIGNERS is empty"):
        FZ.verify_frozen(tmp_path, 777)                        # production: refused, whatever the files say
    # even with the fixture owner key pinned and a signature check that always says "the owner signed it", the
    # proof must verify: the production OpenTimestamps verifier and the fixture verifier both refuse it
    owner = lambda *a: seam.FIXTURE_OWNER  # noqa: E731
    with seam.trust(tag_signer=owner, timestamp=FZ.OpenTimestampsVerifier()):
        with pytest.raises(FZ.FreezeError, match="not an OpenTimestamps proof"):
            FZ.verify_frozen(tmp_path, 777)
    with seam.trust(tag_signer=owner), pytest.raises(R.RegistrationError, match="does not verify"):
        _admit(nt, hyp, b, tmp_path)


def test_p2a_the_production_timestamp_verifier_fails_closed():
    v = FZ.OpenTimestampsVerifier()
    digest = hashlib.sha256(b"manifest").digest()
    well_formed = FZ.OTS_MAGIC + bytes([0x01, FZ.OTS_SHA256]) + digest + b"\x00attestations"
    with pytest.raises(FZ.FreezeError, match="cannot be verified"):
        v.verify(well_formed, digest)                          # a proof of this manifest: still not verifiable here
    with pytest.raises(FZ.FreezeError, match="another file"):
        v.verify(well_formed, hashlib.sha256(b"other").digest())
    for bad in (b"not a proof", b"", FZ.OTS_MAGIC + b"\x02\x08" + digest, seam.FIXTURE_OTS_PREFIX + digest):
        with pytest.raises(FZ.FreezeError, match="not a"):
            v.verify(bad, digest)


def test_p2a_the_git_tag_check_needs_a_valid_signature_on_this_manifest(tmp_path):
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "tag.gpgSign=false"]
    subprocess.run(git + ["init", "-q", str(tmp_path)], check=True)
    m = tmp_path / "AB-0001" / FZ.MANIFEST
    m.parent.mkdir()
    m.write_bytes(b"{}")
    subprocess.run(git + ["add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(git + ["commit", "-q", "--no-gpg-sign", "-m", "fixture"], cwd=tmp_path, check=True)
    subprocess.run(git + ["tag", "-a", "manhattan-batch-0001", "-m", "unsigned fixture tag"], cwd=tmp_path, check=True)
    assert FZ.git_tag_signer("manhattan-batch-0001", tmp_path, m, b"{}") is None         # annotated, not signed
    assert FZ.git_tag_signer("manhattan-batch-0002", tmp_path, m, b"{}") is None         # no such tag


# ------------------------------------------------------------------------------------------------ P2-b

def test_p2b_a_tag_signed_by_a_key_that_is_not_pinned_is_refused(tmp_path, nt, cm):
    hyp, b = _batch(tmp_path, nt, cm, 778)
    seam.freeze_fixture(tmp_path, 778, signer=seam.FIXTURE_OTHER)      # a valid signature by an unpinned key
    with seam.trust():
        with pytest.raises(FZ.FreezeError, match=f"signed by {seam.FIXTURE_OTHER}, which is not a pinned owner key"):
            FZ.verify_frozen(tmp_path, 778)
        with pytest.raises(R.RegistrationError, match="not a pinned owner key"):
            _admit(nt, hyp, b, tmp_path)
    seam.freeze_fixture(tmp_path, 778, signer=seam.FIXTURE_OWNER, ots=False)
    with seam.trust(signers={seam.FIXTURE_OTHER}), pytest.raises(FZ.FreezeError, match="not a pinned owner key"):
        FZ.verify_frozen(tmp_path, 778)                         # the owner's key, when it is not the pinned one
    with pytest.raises(FZ.FreezeError, match="ALLOWED_FREEZE_SIGNERS is empty"):
        FZ.verify_frozen(tmp_path, 778)                         # and production pins no key at all


def test_p2b_the_production_pin_is_empty():
    assert FZ.ALLOWED_FREEZE_SIGNERS == frozenset() and FZ._PRODUCTION.signers == frozenset()
    tree = ast.parse((ROOT / "manhattan/freeze.py").read_text(encoding="utf-8"))
    pins = [n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign))
            and any(isinstance(t, ast.Name) and t.id == "ALLOWED_FREEZE_SIGNERS"
                    for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))]
    assert len(pins) == 1 and ast.unparse(pins[0].value) == "frozenset()"
    fingerprint = re.compile(r"\b[0-9A-Fa-f]{40}\b|SHA256:[A-Za-z0-9+/]{43}")
    for p in [ROOT / "manhattan/freeze.py", *sorted((ROOT / "config").glob("manhattan*.yaml"))]:
        assert not fingerprint.search(p.read_text(encoding="utf-8")), p


# ------------------------------------------------------------------------------------------------ P2-c

def test_p2c_the_fixture_owner_key_and_a_valid_fixture_proof_are_admitted(tmp_path, nt, cm):
    hyp, b = _batch(tmp_path, nt, cm, 779)
    seam.freeze_fixture(tmp_path, 779)
    with seam.trust():
        assert FZ.verify_frozen(tmp_path, 779, expected_manifest_hash=b.manifest_hash)["batch"] == 779
        exp = _admit(nt, hyp, b, tmp_path)
        assert exp.batch == "AB-0779" and R.issued(exp)
        (tmp_path / b.id / FZ.TIMESTAMP_PROOF).write_bytes(seam.FIXTURE_OTS_PREFIX + b"\x00" * 32)
        with pytest.raises(R.RegistrationError, match="does not verify"):
            R.run_selection(SS.sector_world(), exp, cm)        # the freeze is re-verified on every use
    with pytest.raises(R.RegistrationError, match="ALLOWED_FREEZE_SIGNERS is empty"):
        R.run_selection(SS.sector_world(), exp, cm)            # outside the seam, the handle is refused too


# ------------------------------------------------------------------------------------------------ P2-d

CHILD = r'''
import json, sys
from datetime import date
from pathlib import Path
sys.path[:0] = [sys.argv[1] + "/tests", sys.argv[1]]  # the repository and tests/ (the test-only seam)
import manhattan_freeze_seam as seam
from manhattan import ledger as L, roles
from manhattan.equities import catalogue as C, registration as R, sector_synthetic as SS
from manhattan.equities.costs import EquityCostModel
base, number, ledger_path, hyp = Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]), json.loads(sys.argv[5])
cm = EquityCostModel(**json.loads(sys.argv[6]))
fence = roles.Fence(exploration_end=date(2006, 12, 29), enabled=True,
                    reserve={"equities:non_technology_equities": (date(2007, 1, 1), date(2009, 6, 30))})
entry = next(f for f in C.load(C.NT_PATH)["families"] if f["id"] == "NT-M01")
with seam.trust():
    exp = R.admit(entry, hyp, programme="non_technology_equities", batch_dir=base, batch_number=number,
                  manifest_hash=sys.argv[7], code_version="c" * 40)
    world = SS.sector_world()
    lock = R.run_selection(world, exp, cm)
    try:
        v = R.run_holdout(world, exp, lock, cm, ledger=L.Ledger(ledger_path, writer="test fixture",
                                                                protocol="0" * 64),
                          fence=fence, code_version={"commit": "c" * 40, "engine_sha256": "e" * 64})
        print(json.dumps({"status": "read", "rejected": v["rejected"], "attempt": v["ledger"]["attempt_id"]}))
    except R.RegistrationError as e:
        print(json.dumps({"status": "refused", "error": str(e)}))
'''


def test_p2d_two_processes_get_exactly_one_look(tmp_path, nt, cm):
    base, book = tmp_path / "batches", tmp_path / "ledger.jsonl"
    hyp, b = _batch(base, nt, cm, 777)
    seam.freeze_fixture(base, 777)
    script = tmp_path / "child.py"
    script.write_text(CHILD)
    args = [sys.executable, str(script), str(ROOT), str(base), "777", str(book), json.dumps(hyp, default=str),
            json.dumps(COSTS), b.manifest_hash]
    out = []
    for _ in range(2):                                          # two separate OS processes, one after the other
        p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=600)
        assert p.returncode == 0, p.stderr[-2000:]
        out.append(json.loads(p.stdout.strip().splitlines()[-1]))
    assert out[0]["status"] == "read"
    assert out[1]["status"] == "refused" and "one look" in out[1]["error"]
    starts = _starts(book)
    assert len(starts) == 1 and starts[0]["hash"] == out[0]["attempt"]
    p0 = starts[0]["payload"]
    assert (p0["role"], p0["designated"], p0["batch"], p0["window"]["id"]) == ("reserve", True, "AB-0777",
                                                                               HOLDOUT_WINDOW)
    assert _ledger(book).designated_reserve_starts("AB-0777", DOMAIN) == [out[0]["attempt"]]
    assert L.verify(book) == []


# ------------------------------------------------------------------------------------------------ P2-e

def test_p2e_no_reset_by_clearing_a_new_handle_or_a_reload(tmp_path, nt, cm):
    assert not hasattr(R, "_HOLDOUT_READ") and not hasattr(R, "_ISSUED")       # no in-memory guard to clear
    base, book = tmp_path / "batches", tmp_path / "ledger.jsonl"
    hyp, b = _batch(base, nt, cm, 780)
    seam.freeze_fixture(base, 780)
    world = SS.sector_world()
    kw = dict(fence=FENCE, code_version=CV)
    with seam.trust():
        exp = _admit(nt, hyp, b, base)
        lock = R.run_selection(world, exp, cm)
        R.run_holdout(world, exp, lock, cm, ledger=_ledger(book), **kw)
        exp2 = _admit(nt, hyp, b, base)                          # a new admission of the same registration
        with pytest.raises(R.RegistrationError, match="one look"):
            R.run_holdout(world, exp2, R.run_selection(world, exp2, cm), cm, ledger=_ledger(book), **kw)
        importlib.reload(R)                                     # a module reload
        exp3 = _admit(nt, hyp, b, base)
        with pytest.raises(R.RegistrationError, match="one look"):
            R.run_holdout(world, exp3, R.run_selection(world, exp3, cm), cm, ledger=_ledger(book), **kw)
    assert len(_starts(book)) == 1


# ------------------------------------------------------------------------------------------------ P2-f

def test_p2f_forged_selection_locks_and_handles_are_refused(tmp_path, nt, cm):
    base, book = tmp_path / "batches", tmp_path / "ledger.jsonl"
    hyp, b = _batch(base, nt, cm, 781)
    seam.freeze_fixture(base, 781)
    world = SS.sector_world()
    kw = dict(ledger=_ledger(book), fence=FENCE, code_version=CV)
    with seam.trust():
        exp = _admit(nt, hyp, b, base)
        real = R.run_selection(world, exp, cm)
        rows = json.loads(real.in_sample)
        other = 63 if real.chosen_lookback == 126 else 126
        forged = [
            (R.SelectionLock(exp.spec_hash, 252, 2, real.in_sample), "not a declared variant of the registered grid"),
            (R.SelectionLock(exp.spec_hash, 126, 0, "{}"), r"variant count \(0\) disagrees"),   # the S17 forged lock
            (R.SelectionLock(exp.spec_hash, real.chosen_lookback, 3, real.in_sample), r"variant count \(3\)"),
            (R.SelectionLock(exp.spec_hash, real.chosen_lookback, 2, json.dumps({"63": rows["63"]})),
             "one row per registered variant"),
            (R.SelectionLock(exp.spec_hash, other, 2, real.in_sample), "selection rule's choice"),
        ]
        for lock, why in forged:
            with pytest.raises(R.RegistrationError, match="selection lock"):
                R.run_holdout(world, exp, lock, cm, **kw)        # not issued by run_selection
            with pytest.raises(R.RegistrationError, match=why):
                R.run_holdout(world, exp, seam.mint(lock), cm, **kw)     # sealed, but contradicting the registration
        fake = R.ExperimentHandle(exp.spec_hash, exp.family_hash, exp.canonical, NT, "NT-M01", "AB-0782",
                                  exp.manifest_hash, exp.executables, str(base), 782)
        with pytest.raises(R.RegistrationError, match="not an admitted"):
            R.run_selection(world, fake, cm)
        with pytest.raises(R.RegistrationError, match="freeze does not verify"):
            R.run_selection(world, seam.mint(fake), cm)          # sealed, but no frozen batch AB-0782 holds it
    assert _starts(book) == []                                   # nothing was recorded, nothing was read
    with pytest.raises(EquityDataError, match="only this package's synthetic generators"):
        SY.mark_synthetic(object())                               # S17: any object could be marked synthetic


# ------------------------------------------------------------------------------------------------ P2-g

def test_p2g_a_2023_2026_holdout_is_refused_with_mains_configuration(tmp_path, nt, cm):
    w = dict(selection_end=date(2022, 12, 30), holdout_start=date(2023, 1, 3), holdout_end=date(2026, 9, 30))
    base, book = tmp_path / "batches", tmp_path / "ledger.jsonl"
    hyp, b = _batch(base, nt, cm, 783, windows=w)
    seam.freeze_fixture(base, 783)
    world = SS.sector_world()
    main = roles.Fence.from_config(MC.load())
    assert main.enabled is False and main.reserve == {}
    with seam.trust():
        exp = _admit(nt, hyp, b, base)
        lock = R.run_selection(world, exp, cm)
        with pytest.raises(R.RegistrationError, match="not authorized"):
            R.run_holdout(world, exp, lock, cm, ledger=_ledger(book), fence=main, code_version=CV)
        with pytest.raises(R.RegistrationError, match="not authorized"):     # the default fence: the configuration
            R.run_holdout(world, exp, lock, cm, ledger=_ledger(book),       # verified against the code's commit
                          code_version=evaluate.code_version())
        with pytest.raises(R.RegistrationError, match="code identity"):
            R.run_holdout(world, exp, lock, cm, ledger=_ledger(book), fence=FENCE)   # no code identity: refused
        with pytest.raises(R.RegistrationError, match="no ledger"):
            R.run_holdout(world, exp, lock, cm)                  # no ledger: refused before anything else
    assert _starts(book) == []


# ------------------------------------------------------------------------------------------------ P2-h

def test_p2h_run_sleeve_outside_the_gate_reads_no_holdout(cm):
    world = SS.sector_world()
    cfg = TC.CompareConfig(is_end=date(2006, 12, 29), lookbacks=(63, 126, 252))
    for end in (date(2008, 12, 31), date(2006, 12, 30), None):
        with pytest.raises(EquityDataError, match="selection window"):
            TC.run_sleeve(world, cfg, cm, {NT: 126}, name="direct", end=end)
    assert TC.run_sleeve(world, cfg, cm, {NT: 126}, name="selection", end=cfg.is_end).days[-1] <= cfg.is_end


# ------------------------------------------------------------------------------------------------ C10

@pytest.mark.parametrize("fid", ["NT-V01", "NT-Q01", "NT-R01", "NT-L01"])
def test_c10_a_family_without_an_executable_signal_cannot_be_registered(nt, cm, fid):
    with pytest.raises(R.RegistrationError, match=f"no executable signal implements family {fid}"):
        _spec(nt, cm, 790, fid=fid)


def test_c10_the_momentum_families_still_register(nt, cm):
    assert _spec(nt, cm, 790)["catalogue_id"] == "NT-M01"


# ------------------------------------------------------------------------------------------------ static

PRIVATE = {                        # private names of a module, and the other production modules allowed to use them
    "manhattan.freeze": ({"_TRUST", "_Trust", "_PRODUCTION", "_verify"}, ()),
    "manhattan.equities.registration": ({"_mint", "_HANDLE_KEY", "_seal_of"}, ()),
    "manhattan.equities.synthetic": ({"_register", "_SYNTHETIC", "_provenance"}, ()),
    "manhattan.equities.track_compare": ({"_sleeve"}, ("manhattan.equities.registration",)),
}


def _module_name(p: Path) -> str:
    parts = list(p.relative_to(ROOT).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _private_uses(p: Path) -> list:
    """(module, name) for every private name of ``PRIVATE`` that the file ``p`` imports or reads as an attribute."""
    me = _module_name(p)
    package = me if p.name == "__init__.py" else me.rpartition(".")[0]
    tree = ast.parse(p.read_text(encoding="utf-8"))
    alias, out = {}, []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.asname:
                    alias[a.asname] = a.name
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            if n.level:
                pkg = package.split(".")
                base = ".".join(pkg[:len(pkg) - n.level + 1] + ([n.module] if n.module else []))
            for a in n.names:
                full = f"{base}.{a.name}"
                if full in PRIVATE:
                    alias[a.asname or a.name] = full
                if base in PRIVATE and a.name in PRIVATE[base][0]:
                    out.append((base, a.name))
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute):
            v = n.value
            name = alias.get(v.id) if isinstance(v, ast.Name) else None
            if isinstance(v, ast.Attribute):            # manhattan.freeze._TRUST
                name = ast.unparse(v)
            if name in PRIVATE and n.attr in PRIVATE[name][0]:
                out.append((name, n.attr))
    return [(m, x) for m, x in out if m != me and me not in PRIVATE[m][1]]


def test_static_no_production_module_references_the_test_seam_or_the_private_trust():
    bad = []
    for p in sorted((ROOT / "manhattan").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(encoding="utf-8")
        if "manhattan_freeze_seam" in text:
            bad.append((rel, "manhattan_freeze_seam"))
        bad += [(rel, f"{m}.{x}") for m, x in _private_uses(p)]
        if rel not in ("manhattan/equities/synthetic.py", "manhattan/equities/sector_synthetic.py") and \
                re.search(r"\bmark_synthetic\b", text):
            bad.append((rel, "mark_synthetic"))
    assert bad == []
    # the scan sees the uses it must see
    seam_file = ROOT / "tests/manhattan_freeze_seam.py"
    assert {("manhattan.freeze", "_TRUST"), ("manhattan.equities.registration", "_mint"),
            ("manhattan.equities.synthetic", "_register")} <= set(_private_uses(seam_file))
    assert ("manhattan.equities.track_compare", "_sleeve") not in _private_uses(
        ROOT / "manhattan/equities/registration.py")                                # an allowed caller
