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

Review of PR #106: a real GPG-signed tag verifies with ``root`` = the batches directory, and a signed tag on a
commit holding another manifest is refused (mutation M5); the holdout is read only after its ledger start (M12);
``run_sleeve`` cuts at the registered selection end, and the out-of-sample report is private; the single look is per
ledger file (a stated limitation); a marked world is frozen; the private names are in the name-based scan of
``tests/test_manhattan_binding_access.py``.

Synthetic only: every batch, signature, timestamp proof, fence and ledger is a fixture in a temporary directory.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import inspect
import json
import re
import subprocess
import sys
from datetime import date, datetime
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


def _gpg_repo(tmp_path, monkeypatch):
    """A temporary repository and a throwaway GPG key in a temporary GNUPGHOME (test fixture key, never pinned in
    production). Returns (git command prefix, repository, fingerprint)."""
    import shutil
    import tempfile
    if not shutil.which("gpg"):
        pytest.skip("gpg is not installed")
    home = tempfile.mkdtemp(prefix="gpg")            # short path: gpg-agent's socket lives there
    monkeypatch.setenv("GNUPGHOME", home)
    subprocess.run(["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "", "--quick-gen-key",
                    "Manhattan test fixture <fixture@example.invalid>", "ed25519", "sign", "never"],
                   check=True, capture_output=True)
    cols = subprocess.run(["gpg", "--batch", "--list-keys", "--with-colons"], check=True, capture_output=True,
                          text=True).stdout
    fpr = next(line.split(":")[9] for line in cols.splitlines() if line.startswith("fpr:"))
    repo = tmp_path / "repo"
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", f"user.signingkey={fpr}",
           "-c", "gpg.program=gpg", "-c", "gpg.format=openpgp", "-c", "commit.gpgSign=false"]
    subprocess.run(git + ["init", "-q", str(repo)], check=True)
    return git, repo, fpr, home


def _gpg_cleanup(home):
    import os
    import shutil
    subprocess.run(["gpgconf", "--kill", "gpg-agent"], env={**os.environ, "GNUPGHOME": home}, capture_output=True)
    shutil.rmtree(home, ignore_errors=True)


def _commit_and_sign(git, repo, number):
    subprocess.run(git + ["add", "-A"], cwd=repo, check=True)
    subprocess.run(git + ["commit", "-q", "-m", f"batch {number}"], cwd=repo, check=True)
    subprocess.run(git + ["tag", "-s", FZ.TAG.format(n=number), "-m", "fixture"], cwd=repo, check=True,
                   capture_output=True)


def test_a_real_signed_tag_verifies_from_the_batches_directory(tmp_path, monkeypatch, nt, cm):
    git, repo, fpr, home = _gpg_repo(tmp_path, monkeypatch)
    try:
        batches = repo / "data" / "manhattan" / "batches"          # root defaults to the batches directory
        hyp, b = _batch(batches, nt, cm, 784)
        m = batches / b.id / FZ.MANIFEST
        _commit_and_sign(git, repo, 784)
        assert FZ.git_tag_signer(FZ.TAG.format(n=784), batches, m, m.read_bytes()) == fpr
        assert FZ.git_tag_signer(FZ.TAG.format(n=784), repo, m, m.read_bytes()) == fpr
        seam.stamp(batches, 784)
        with seam.trust(signers={fpr}, tag_signer=FZ.git_tag_signer):    # a fixture pin of this throwaway key
            assert FZ.verify_frozen(batches, 784, expected_manifest_hash=b.manifest_hash)["batch"] == 784
            assert _admit(nt, hyp, b, batches).batch == "AB-0784"
        with seam.trust(tag_signer=FZ.git_tag_signer), pytest.raises(FZ.FreezeError, match="not a pinned owner"):
            FZ.verify_frozen(batches, 784)                     # a valid signature, but not by the pinned key
        with pytest.raises(FZ.FreezeError, match="ALLOWED_FREEZE_SIGNERS is empty"):
            FZ.verify_frozen(batches, 784)                     # production: nothing pinned
    finally:
        _gpg_cleanup(home)


def test_m5_a_signed_tag_on_a_commit_holding_another_manifest_is_refused(tmp_path, monkeypatch, nt, cm):
    git, repo, fpr, home = _gpg_repo(tmp_path, monkeypatch)
    try:
        batches = repo / "batches"
        _batch(batches, nt, cm, 785)
        _commit_and_sign(git, repo, 785)                        # the tag signs this first manifest
        import shutil
        shutil.rmtree(batches / "AB-0785")
        hyp, b = _batch(batches, nt, cm, 785, windows={**WINDOWS, "holdout_end": date(2008, 6, 30)})
        m = batches / b.id / FZ.MANIFEST
        assert FZ.git_tag_signer(FZ.TAG.format(n=785), batches, m, m.read_bytes()) is None
        seam.stamp(batches, 785)
        with seam.trust(signers={fpr}, tag_signer=FZ.git_tag_signer):
            with pytest.raises(FZ.FreezeError, match="does not hold this manifest"):
                FZ.verify_frozen(batches, 785)
    finally:
        _gpg_cleanup(home)


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
    book = L.Ledger(ledger_path, writer="test fixture", protocol="0" * 64)
    if len(sys.argv) > 8:
        import time
        ready, peer_ready = map(Path, sys.argv[8:10])
        ready.touch()
        deadline = time.monotonic() + 90
        while not peer_ready.exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("the other process did not open the ledger")
            time.sleep(0.01)
    try:
        v = R.run_holdout(world, exp, lock, cm, ledger=book,
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


def test_simultaneous_synthetic_holdout_starts_share_one_ledger(tmp_path, nt, cm):
    base, book = tmp_path / "batches", tmp_path / "ledger.jsonl"
    hyp, batch = _batch(base, nt, cm, 777)
    seam.freeze_fixture(base, 777)
    script = tmp_path / "child.py"
    script.write_text(CHILD)
    book.touch()
    alias = tmp_path / "alias.jsonl"
    alias.symlink_to(book)
    ready = [tmp_path / "first.ready", tmp_path / "second.ready"]

    # Both children open the same empty ledger before either attempts registration.
    children = []
    try:
        for i, path in enumerate((book, alias)):
            args = [sys.executable, str(script), str(ROOT), str(base), "777", str(path),
                    json.dumps(hyp, default=str), json.dumps(COSTS), batch.manifest_hash,
                    str(ready[i]), str(ready[1 - i])]
            children.append(subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE, text=True))
        outcomes = []
        for child in children:
            stdout, stderr = child.communicate(timeout=120)
            assert child.returncode == 0, stderr[-2000:]
            outcomes.append(json.loads(stdout.strip().splitlines()[-1]))
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.communicate()

    assert sorted(o["status"] for o in outcomes) == ["read", "refused"]
    accepted = next(o for o in outcomes if o["status"] == "read")
    refused = next(o for o in outcomes if o["status"] == "refused")
    assert "stale ledger handle" in refused["error"]
    assert [r["hash"] for r in _starts(book)] == [accepted["attempt"]]
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


def test_known_limitation_the_single_look_is_per_ledger_file(tmp_path, nt, cm):
    """Documented, not fixed here (PR #86 property; run_holdout's docstring): the designation lives in the ledger it
    is recorded in, so a look recorded in another ledger file is not refused. The guarantee needs the one
    authoritative ledger (owner decisions A-1/A-2). If this starts failing, the limitation was closed: update the
    docstring."""
    base = tmp_path / "batches"
    hyp, b = _batch(base, nt, cm, 788)
    seam.freeze_fixture(base, 788)
    world = SS.sector_world()
    with seam.trust():
        exp = _admit(nt, hyp, b, base)
        lock = R.run_selection(world, exp, cm)
        for name in ("ledger-a.jsonl", "ledger-b.jsonl"):
            R.run_holdout(world, exp, lock, cm, ledger=_ledger(tmp_path / name), fence=FENCE, code_version=CV)
    assert len(_starts(tmp_path / "ledger-a.jsonl")) == len(_starts(tmp_path / "ledger-b.jsonl")) == 1
    assert "One look per ledger file" in R.run_holdout.__doc__


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

def test_p2h_run_sleeve_outside_the_gate_reads_no_holdout(tmp_path, nt, cm):
    world = SS.sector_world()
    # the review's bypass: a caller configuration whose is_end is the end of the holdout (519 holdout days before)
    cfg = TC.CompareConfig(is_end=date(2008, 12, 31), lookbacks=(63, 126, 252))
    with pytest.raises((EquityDataError, TypeError)):
        TC.run_sleeve(world, cfg, cm, {NT: 126}, name="direct", end=date(2008, 12, 31))
    assert not hasattr(TC, "compare")                          # the out-of-sample report is private (_compare)
    base = tmp_path / "batches"
    hyp, b = _batch(base, nt, cm, 786)
    seam.freeze_fixture(base, 786)
    with seam.trust():
        exp = _admit(nt, hyp, b, base)
        for end in (date(2008, 12, 31), date(2007, 1, 2), date(2006, 12, 30), datetime(2006, 12, 29, 23)):
            with pytest.raises(EquityDataError, match="registered selection window"):
                TC.run_sleeve(world, exp, cm, 126, name="direct", end=end)     # the cutoff is the registered spec's
        with pytest.raises(EquityDataError, match="not a declared variant"):
            TC.run_sleeve(world, exp, cm, 252, name="direct")
        with pytest.raises(R.RegistrationError, match="cost model differs"):
            TC.run_sleeve(world, exp, EquityCostModel(**{**COSTS, "impact": 0.0}), 126, name="direct")
        sl = TC.run_sleeve(world, exp, cm, 126, name="selection")
        assert sl.days[-1] <= WINDOWS["selection_end"]
    with pytest.raises(R.RegistrationError, match="ALLOWED_FREEZE_SIGNERS is empty"):
        TC.run_sleeve(world, exp, cm, 126, name="direct")        # production: the handle's freeze does not verify


def test_m12_the_holdout_is_read_only_after_its_ledger_start(tmp_path, nt, cm):
    """Mutation M12 (the look registered after the holdout read) fails here: any read dated in the holdout before
    the ledger holds the look's start raises."""
    base, book = tmp_path / "batches", tmp_path / "ledger.jsonl"
    hyp, b = _batch(base, nt, cm, 787)
    seam.freeze_fixture(base, 787)
    w = SS.sector_world()
    reads = []

    class Guard:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            attr = getattr(self._inner, name)
            if not callable(attr):
                return attr

            def guarded(*args, **kw):
                for v in list(args) + list(kw.values()):
                    if isinstance(v, date) and v >= WINDOWS["holdout_start"]:
                        if not _starts(book):
                            raise AssertionError(f"{name} read {v} before the holdout look was recorded")
                        reads.append(v)
                return attr(*args, **kw)
            return guarded

    guarded = seam.mark_synthetic(dataclasses.replace(w, prices=Guard(w.prices)), "M12 instrumented world")
    with seam.trust():
        exp = _admit(nt, hyp, b, base)
        lock = R.run_selection(guarded, exp, cm)
        assert reads == []                                       # selection read nothing in the holdout
        R.run_holdout(guarded, exp, lock, cm, ledger=_ledger(book), fence=FENCE, code_version=CV)
    assert reads and len(_starts(book)) == 1


def test_a_marked_world_cannot_be_changed_afterwards():
    w = SS.sector_world()
    with pytest.raises(dataclasses.FrozenInstanceError):
        w.prices = None
    assert SY.provenance(w) == SY.provenance(SS.sector_world()) != SY.provenance(SS.sector_world(seed=103))


# ------------------------------------------------------------------------------------------------ C10

@pytest.mark.parametrize("fid", ["NT-V01", "NT-Q01", "NT-R01", "NT-L01"])
def test_c10_a_family_without_an_executable_signal_cannot_be_registered(nt, cm, fid):
    with pytest.raises(R.RegistrationError, match=f"no executable signal implements family {fid}"):
        _spec(nt, cm, 790, fid=fid)


def test_c10_the_momentum_families_still_register(nt, cm):
    assert _spec(nt, cm, 790)["catalogue_id"] == "NT-M01"


# ------------------------------------------------------------------------------------------------ static

PR2_NAMES = ("_TRUST", "_PRODUCTION", "_Trust", "_verify_batch", "_mint", "_HANDLE_KEY", "_seal_of", "_sealed",
             "_SYNTHETIC", "_register_world", "_world_provenance", "_GENERATORS", "_sleeve", "_compare",
             "manhattan_freeze_seam")


def test_static_no_production_module_references_the_test_seam_or_the_private_trust():
    from test_manhattan_binding_access import ALLOWED, scan
    assert set(PR2_NAMES) <= set(ALLOWED)                          # pinned in the one name-based allowlist
    sources = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8")
               for p in sorted((ROOT / "manhattan").rglob("*.py"))}
    assert {k: v for k, v in scan(sources).items() if k in PR2_NAMES} == {}
    # the scan sees what the seam reaches, wherever it would sit under manhattan/
    found = scan({"manhattan/ops/rogue.py": (ROOT / "tests/manhattan_freeze_seam.py").read_text(encoding="utf-8")})
    assert {"_TRUST", "_PRODUCTION", "_Trust", "_mint", "_register_world"} <= set(found)
    bad = [rel for rel, text in sources.items()
           if rel not in ("manhattan/equities/synthetic.py", "manhattan/equities/sector_synthetic.py")
           and re.search(r"\bmark_synthetic\b", text)]
    assert bad == []
