"""Manhattan ops, component 4: the durable private ledger (O-14 to O-21). A local bare repository stands in for the
private repository manhattan-ledger and another for the mirror. No network."""
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from manhattan.ops import store as ST

T0 = datetime(2026, 11, 16, 23, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


def bare(path: Path) -> str:
    git("init", "-q", "--bare", "-b", "main", str(path))
    return str(path)


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        self.t += timedelta(seconds=1)
        return self.t


def store(tmp_path, remote, name, run_id="1", attempt=1, clock=None, **kw):
    return ST.Store(workdir=tmp_path / name, remote=remote, run_id=run_id, run_attempt=attempt, commit="c" * 40,
                    clock=clock or Clock(), **kw).open()


def obs(pred, day, net):
    return ST.Intent("observation", ("observation", pred, day), {"net": net, "data_hash": "d" * 64},
                     source="synthetic", retrieved_utc="2026-11-16T22:30:00Z")


BATCH_A = [obs("AP-1", "2026-11-16", 0.0123456789), obs("AP-2", "2026-11-16", -0.0098765432),
           obs("AP-3", "2026-11-16", 0.0011223344), obs("AP-4", "2026-11-16", -0.0055667788)]
BATCH_B = [ST.Intent("heartbeat", ("heartbeat", "2026-11-16"), {"asof": "2026-11-16"})]


# ---- O-14, O-16: provenance, chain, idempotency

def test_records_carry_provenance_and_a_nonce_and_the_chain_verifies(tmp_path):
    s = store(tmp_path, bare(tmp_path / "remote.git"), "a")
    res = s.write(BATCH_A, "obs")
    assert res["appended"] == 4
    r = s.get(("observation", "AP-1", "2026-11-16"))
    assert set(r["provenance"]) == set(ST.PROVENANCE) and r["provenance"]["run_id"] == "1"
    assert r["provenance"]["source"] == "synthetic" and r["provenance"]["retrieved_utc"] == "2026-11-16T22:30:00Z"
    assert re.fullmatch(r"[0-9a-f]{32}", r["nonce"])
    assert ST.verify_chain(s.records) == []
    fresh = store(tmp_path, s.remote, "b")
    assert [x["hash"] for x in fresh.records] == [x["hash"] for x in s.records]


def test_same_content_is_a_no_op_and_different_content_is_a_conflict(tmp_path):
    s = store(tmp_path, bare(tmp_path / "remote.git"), "a")
    s.write(BATCH_A, "obs")
    before = [json.dumps(r, sort_keys=True) for r in s.records]
    again = s.write(BATCH_A, "obs")
    assert again["skipped"] and len(s.records) == 4
    other = s.write([obs("AP-1", "2026-11-16", 0.5)], "overwrite attempt")
    assert other["conflict"] == 1 and other["appended"] == 0
    assert [json.dumps(r, sort_keys=True) for r in s.records[:4]] == before        # the first record stands
    c = s.of_type("conflict")
    assert len(c) == 1 and c[0]["payload"]["existing_hash"] == s.records[0]["hash"]
    s.write([obs("AP-1", "2026-11-16", 0.5)], "overwrite attempt 2")                # the conflict is recorded once
    assert len(s.of_type("conflict")) == 1


def test_any_edit_or_removal_breaks_the_chain(tmp_path):
    s = store(tmp_path, bare(tmp_path / "remote.git"), "a")
    s.write(BATCH_A, "obs")
    recs = s.records
    edited = [dict(r) for r in recs]
    edited[1] = {**edited[1], "payload": {**edited[1]["payload"], "net": "0.5"}}
    assert "edited" in ST.verify_chain(edited)[0]
    assert "seq" in ST.verify_chain(recs[:1] + recs[2:])[0]
    assert "anchor" in ST.verify_chain(recs[:3], anchor=recs[-1]["hash"])[0]


def test_a_rewritten_remote_is_refused_on_open(tmp_path):
    remote = bare(tmp_path / "remote.git")
    s = store(tmp_path, remote, "a")
    s.write(BATCH_A, "obs")
    lines = (s.workdir / ST.CHAIN).read_text().splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["net"] = "0.9"                                          # what a stolen key could do
    lines[0] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    (s.workdir / ST.CHAIN).write_text("\n".join(lines) + "\n")
    git("commit", "-qam", "tamper", cwd=s.workdir)
    git("push", "-q", "--force", "origin", "HEAD:main", cwd=s.workdir)    # the test plays the attacker, not the code
    with pytest.raises(ST.StoreError, match="does not verify"):
        store(tmp_path, remote, "b")


# ---- O-18: the journal

def test_journal_goes_pending_committed_verified(tmp_path):
    s = store(tmp_path, bare(tmp_path / "remote.git"), "a")
    res = s.write(BATCH_A, "obs")
    states = [j["state"] for j in s.journal() if j["entry"] == res["entry"]]
    assert states == ["pending", "committed", "verified"] and s.unfinished() == []


# ---- O-17: a lost race is retried by re-appending, never by force

def test_non_fast_forward_is_retried_by_reappending(tmp_path):
    remote = bare(tmp_path / "remote.git")
    s = store(tmp_path, remote, "a")
    s.write(BATCH_B, "heartbeat")
    other = store(tmp_path, remote, "other", run_id="9")
    raced = {"done": False}

    def race(st, _):
        if not raced["done"]:
            raced["done"] = True
            other.open()
            other.write([obs("AP-9", "2026-11-16", 0.0777777777)], "other writer")

    s.before_push = race
    s.write(BATCH_A, "obs")
    assert False in s.pushes                                          # a push was rejected...
    final = store(tmp_path, remote, "check")
    keys = {tuple(r["key"]) for r in final.records}
    assert ("observation", "AP-9", "2026-11-16") in keys                # ...the other writer's record survived
    assert {tuple(i.key) for i in BATCH_A} <= keys
    assert ST.verify_chain(final.records) == []


def test_no_force_push_anywhere_in_the_ops_code():
    for p in sorted((ROOT / "manhattan/ops").glob("*.py")):
        src = p.read_text()
        for bad in ("--force", "--force-with-lease", '"+HEAD', "'+HEAD", '"+refs', "'+refs", '"-f"', "--mirror"):
            assert bad not in src, f"{p.name} contains {bad}"


# ---- O-15: locks

def test_live_lock_stops_another_run_and_expired_lock_is_broken(tmp_path):
    remote = bare(tmp_path / "remote.git")
    clock = Clock()
    a = store(tmp_path, remote, "a", run_id="1", clock=clock)
    assert a.acquire()["status"] == "acquired"
    b = store(tmp_path, remote, "b", run_id="2", clock=clock)
    with pytest.raises(ST.Locked):
        b.acquire()
    clock.t += timedelta(hours=2)
    b.open()
    got = b.acquire()
    assert got == {"status": "acquired", "broken": 1}
    assert b.of_type("lock_broken")[0]["payload"]["broken_by"] == ["2", "1"]


def test_rerun_attempt_breaks_its_own_earlier_attempt(tmp_path):
    remote = bare(tmp_path / "remote.git")
    store(tmp_path, remote, "a", run_id="7", attempt=1).acquire()
    b = store(tmp_path, remote, "b", run_id="7", attempt=2)
    assert b.acquire()["broken"] == 1


def test_lost_lock_race_sees_the_winner(tmp_path):
    remote = bare(tmp_path / "remote.git")
    a = store(tmp_path, remote, "a", run_id="1")
    b = store(tmp_path, remote, "b", run_id="2")
    b.before_push = lambda st, _: (a.acquire() if not a.active_locks() else None)
    with pytest.raises(ST.Locked):
        b.acquire()


def test_release_ends_the_lock(tmp_path):
    remote = bare(tmp_path / "remote.git")
    a = store(tmp_path, remote, "a", run_id="1")
    a.acquire()
    a.release()
    assert a.active_locks() == []
    assert store(tmp_path, remote, "b", run_id="2").acquire()["status"] == "acquired"


# ---- O-19: mirror and verification

def test_mirror_and_verification(tmp_path):
    remote, mirror = bare(tmp_path / "remote.git"), bare(tmp_path / "mirror.git")
    s = store(tmp_path, remote, "a")
    s.write(BATCH_A, "obs")
    assert s.verify_mirror(mirror, tmp_path / "m0")["status"] in ("unreachable", "equal")
    assert s.mirror(mirror)["status"] == "pushed"
    assert s.verify_mirror(mirror, tmp_path / "m1")["status"] == "equal"
    s.write(BATCH_B, "heartbeat")
    assert s.verify_mirror(mirror, tmp_path / "m2")["status"] == "behind"
    s.mirror(mirror)
    assert s.verify_mirror(mirror, tmp_path / "m3")["status"] == "equal"
    # a mirror rewritten behind the runner's back is caught, and the runner does not overwrite it
    m = tmp_path / "m3"
    lines = (m / ST.CHAIN).read_text().splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["net"] = "0.9"
    rec["hash"] = ST.record_hash(rec)
    lines[0] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    (m / ST.CHAIN).write_text("\n".join(lines) + "\n")
    git("-c", "user.name=t", "-c", "user.email=t@e.invalid", "commit", "-qam", "tamper", cwd=m)
    git("push", "-q", "--force", "origin", "HEAD:main", cwd=m)
    assert s.verify_mirror(mirror, tmp_path / "m4")["status"] in ("broken", "diverged")
    s.write([obs("AP-5", "2026-11-17", 0.0012121212)], "more")
    assert s.mirror(mirror)["status"] == "rejected"
    assert s.mirror(None) == {"status": "not_configured"}


# ---- O-21: crash at every stage, then exact recovery

def cycle(st: ST.Store, mirror: str, scratch: Path):
    st.reconcile()
    st.acquire()
    st.write(BATCH_A, "observations", files={"raw/" + "e" * 64 + ".bin": b"raw bytes"})
    st.write(BATCH_B, "heartbeat")
    st.release()
    st.mirror(mirror)
    return st.verify_mirror(mirror, scratch)


def content(records):
    return sorted(json.dumps([r["type"], r["key"], r["payload"]], sort_keys=True) for r in records
                  if r["type"] not in ("lock", "unlock", "lock_broken"))


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ref")
    s = store(tmp, bare(tmp / "remote.git"), "a")
    assert cycle(s, bare(tmp / "mirror.git"), tmp / "scratch")["status"] == "equal"
    return content(s.records)


@pytest.mark.parametrize("stage", ST.STAGES)
def test_crash_at_every_stage_then_exact_recovery(tmp_path, stage, reference):
    remote, mirror = bare(tmp_path / "remote.git"), bare(tmp_path / "mirror.git")
    clock = Clock()
    crashed = store(tmp_path, remote, "crash", run_id="100", clock=clock, crash_at=stage)
    with pytest.raises(ST.SimulatedCrash):
        cycle(crashed, mirror, tmp_path / "s0")
    before = [json.dumps(r, sort_keys=True) for r in store(tmp_path, remote, "peek").records]
    clock.t += timedelta(hours=2)                                        # the next run, after the lock expired
    rec = store(tmp_path, remote, "recover", run_id="101", clock=clock)
    v = cycle(rec, mirror, tmp_path / "s1")
    final = store(tmp_path, remote, "final")
    after = [json.dumps(r, sort_keys=True) for r in final.records]
    assert after[: len(before)] == before                                # nothing written earlier was changed
    assert content(final.records) == reference                           # nothing missing, nothing duplicated
    assert ST.verify_chain(final.records) == [] and v["status"] == "equal"
    assert final.unfinished() == [] and final.active_locks() == []
    assert (final.workdir / "raw" / ("e" * 64 + ".bin")).read_bytes() == b"raw bytes"
    # every stage but the mirror comes before the unlock: the crashed run's lock was broken, not ignored
    assert bool(final.of_type("lock_broken")) == (stage != "mid_mirror")


def test_torn_write_never_reaches_the_remote(tmp_path):
    remote = bare(tmp_path / "remote.git")
    s = store(tmp_path, remote, "a", crash_at="mid_chain_write")
    with pytest.raises(ST.SimulatedCrash):
        s.write(BATCH_A, "obs")
    local = (s.workdir / ST.CHAIN).read_text()
    assert not local.endswith("\n")                                     # the clone holds a torn line...
    remote_view = store(tmp_path, remote, "b")
    assert remote_view.records == [] and len(remote_view.unfinished()) == 1   # ...the remote only the pending entry
