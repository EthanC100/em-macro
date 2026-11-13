"""The durable, recoverable private ledger (criteria O-14 to O-22).

Runner storage on GitHub Actions is ephemeral and is never the only record. The authoritative store is a **private
git repository** (``manhattan-ledger``) that only the runner's deploy key writes. In tests a local bare repository
stands in for it. Its layout:

    chain.jsonl        append-only, hash-chained records (every record type)
    journal.jsonl      the write-ahead journal: pending -> committed -> verified, one line per transition
    raw/<sha256>.bin   first-seen captures of source data, content-addressed
    logs/<run>.log     the run's private log (everything the public log is not allowed to say)
    heartbeat.json     a convenience copy of the last heartbeat (the chain record is authoritative)

**Records.** One JSON line each: ``seq``, ``ts_utc``, ``type``, ``key`` (a list of strings: the idempotency key),
``nonce`` (128 random bits, so a published head hash cannot be brute-forced back to an outcome), ``provenance``
(data source, retrieval time, runner run id and attempt, em-macro commit), ``payload``, ``prev_hash`` and ``hash``
(SHA-256 of the canonical form of all the other fields; ``manhattan.spec.canonical_bytes``).

**Idempotency.** A record's key is unique in the chain. Appending a key that is present with the same content
(type, key, payload) does nothing; with different content it is refused, a ``conflict`` record is written, and the
earlier record stays as it is. For an observation the key is ``("observation", prediction id, observation date)``.

**Writes.** ``write`` puts a batch of intended records through the journal: a ``pending`` line (with the intents) is
committed and pushed first; then the records and a ``committed`` line are committed and pushed together; then the
remote is fetched again and the records are checked there, and a ``verified`` line is pushed. ``reconcile``, run at
the start of every run, finishes every entry that a crash left unfinished. A push rejected as non-fast-forward is
retried by fetching, resetting the local clone to the remote and re-applying the change, never by force-pushing.

**Locks.** A run appends a ``lock`` record and pushes it before anything else; git's fast-forward rule makes this a
compare-and-swap. An unexpired lock of another run stops the run; an expired one is broken by a ``lock_broken``
record. The workflow's concurrency group is the first line of defence; the lock is the second.

**Mirror and verification.** ``mirror`` pushes the ledger to a second git remote by fast-forward only;
``verify_pair`` recomputes both hash chains and checks that the mirror is the primary or a prefix of it.

Private repositories on GitHub Free have no branch protection or rulesets, so the deploy key could rewrite history.
Tamper evidence then rests on the hash chain, the head hash published in each run's public health record, external
timestamps of the head, and the mirror (``docs/manhattan/ops/LEDGER.md``).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from manhattan import spec as S

from . import blinding

GENESIS = "0" * 64
CHAIN, JOURNAL = "chain.jsonl", "journal.jsonl"
FIELDS = ("seq", "ts_utc", "type", "key", "nonce", "provenance", "payload", "prev_hash")
PROVENANCE = ("source", "retrieved_utc", "run_id", "run_attempt", "commit")
STAGES = ("after_lock", "after_journal_local", "after_journal_push", "mid_chain_write", "after_chain_commit_local",
          "after_chain_push", "after_verify", "mid_mirror", "before_unlock")
BRANCH = "main"


class StoreError(RuntimeError):
    pass


class Locked(StoreError):
    pass


class SimulatedCrash(BaseException):
    """Raised at a named stage in crash tests. A BaseException, so no ordinary handler can swallow it."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_hash(rec: dict) -> str:
    return hashlib.sha256(S.canonical_bytes({k: rec[k] for k in FIELDS})).hexdigest()


def content_hash(type_: str, key, payload: dict) -> str:
    """What idempotency compares: the type, the key and the payload (not the nonce, time or provenance)."""
    return hashlib.sha256(S.canonical_bytes({"type": type_, "key": list(key), "payload": payload})).hexdigest()


def _canon(obj):
    return json.loads(S.canonical_bytes(obj))


def read_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_chain(records: list[dict], anchor: str | None = None) -> list[str]:
    """Problems in a chain (empty when intact). Every hash is recomputed; keys must be unique."""
    prev, seen = GENESIS, set()
    for i, rec in enumerate(records, 1):
        if any(k not in rec for k in (*FIELDS, "hash")):
            return [f"record {i}: missing fields"]
        if rec["seq"] != i:
            return [f"record {i}: seq is {rec['seq']} (a record was removed, added or moved)"]
        if rec["prev_hash"] != prev:
            return [f"record {i}: prev_hash does not match the record before it"]
        if rec["hash"] != record_hash(rec):
            return [f"record {i}: hash does not match its content (the record was edited)"]
        k = tuple(rec["key"])
        if k in seen:
            return [f"record {i}: duplicate key {list(k)}"]
        seen.add(k)
        prev = rec["hash"]
    if anchor is not None and prev != anchor:
        return [f"head is {prev}, the anchor says {anchor}"]
    return []


def verify_pair(primary: list[dict], mirror: list[dict]) -> dict:
    """Recompute both chains and compare. ``status``: equal, behind (the mirror is a strict prefix), diverged or
    broken."""
    ep, em = verify_chain(primary), verify_chain(mirror)
    if ep or em:
        return {"status": "broken", "primary_errors": ep, "mirror_errors": em}
    n = len(mirror)
    if n > len(primary) or any(primary[i]["hash"] != mirror[i]["hash"] for i in range(n)):
        return {"status": "diverged"}
    head = lambda rs: rs[-1]["hash"] if rs else GENESIS
    return {"status": "equal" if n == len(primary) else "behind", "primary_head": head(primary),
            "mirror_head": head(mirror), "primary_records": len(primary), "mirror_records": n}


@dataclass
class Intent:
    type: str
    key: tuple
    payload: dict
    source: str = "runner"
    retrieved_utc: str | None = None

    def as_dict(self) -> dict:
        return {"type": self.type, "key": list(self.key), "payload": _canon(self.payload), "source": self.source,
                "retrieved_utc": self.retrieved_utc}

    @classmethod
    def from_dict(cls, d: dict) -> "Intent":
        return cls(d["type"], tuple(d["key"]), d["payload"], d.get("source", "runner"), d.get("retrieved_utc"))


@dataclass
class Store:
    """A clone of the private ledger, and the only way to write it."""
    workdir: Path
    remote: str
    run_id: str = "local"
    run_attempt: int = 1
    commit: str = "unknown"
    clock: Callable[[], datetime] = utcnow
    nonce_fn: Callable[[], str] = blinding.nonce
    crash_at: str | None = None
    before_push: Callable[["Store", str], None] | None = None      # tests: race another writer here
    max_retries: int = 6
    pushes: list = field(default_factory=list)
    _records: list = field(default_factory=list)
    _by_key: dict = field(default_factory=dict)

    # ------------------------------------------------------------ git
    def _git(self, *args, cwd: Path | None = None, check=True, env=None) -> subprocess.CompletedProcess:
        e = {**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})}
        return subprocess.run(["git", *args], cwd=cwd or self.workdir, capture_output=True, text=True, check=check, env=e)

    def open(self) -> "Store":
        """Clone the ledger (or bring an existing clone to the remote's state), load and verify the chain."""
        self.workdir = Path(self.workdir)
        if not (self.workdir / ".git").exists():
            self.workdir.parent.mkdir(parents=True, exist_ok=True)
            self._git("clone", "-q", self.remote, str(self.workdir), cwd=self.workdir.parent)
            self._git("config", "user.name", "manhattan-ops-runner")
            self._git("config", "user.email", "manhattan-ops-runner@users.noreply.github.com")
            self._git("config", "commit.gpgsign", "false")
        self._reset_to_remote()
        return self

    def _remote_has_branch(self) -> bool:
        out = self._git("ls-remote", "--heads", "origin", BRANCH).stdout
        return bool(out.strip())

    def _reset_to_remote(self) -> None:
        """Make the clone equal to the remote: drop local commits that were not pushed and any torn file."""
        if self._remote_has_branch():
            self._git("fetch", "-q", "origin", BRANCH)
            self._git("checkout", "-q", "-B", BRANCH, f"origin/{BRANCH}")
            self._git("reset", "-q", "--hard", f"origin/{BRANCH}")
        else:
            self._git("checkout", "-q", "--orphan", BRANCH, check=False)
            self._git("rm", "-rqf", "--ignore-unmatch", ".", check=False)
        self._git("clean", "-qfdx")
        self._load()

    def _load(self) -> None:
        recs = read_lines(self.workdir / CHAIN)
        errs = verify_chain(recs)
        if errs:
            raise StoreError("the private ledger does not verify: " + "; ".join(errs))
        self._records = recs
        self._by_key = {tuple(r["key"]): r for r in recs}

    def _crash(self, stage: str) -> None:
        if self.crash_at == stage:
            raise SimulatedCrash(stage)

    def _commit(self, message: str) -> bool:
        self._git("add", "-A")
        if not self._git("status", "--porcelain").stdout.strip():
            return False
        self._git("commit", "-q", "-m", message)
        return True

    def _push(self) -> bool:
        """Fast-forward push; False when the remote moved on (non-fast-forward). Never forced."""
        if self.before_push:
            self.before_push(self, "push")
        r = self._git("push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}", check=False)
        self.pushes.append(r.returncode == 0)
        if r.returncode == 0:
            return True
        if "rejected" in r.stderr or "non-fast-forward" in r.stderr or "fetch first" in r.stderr:
            return False
        raise StoreError("push to the private ledger failed (not a race)")

    def _transact(self, message: str, mutate: Callable[[], object], crash_after_commit: str | None = None,
                  crash_after_push: str | None = None):
        """Apply ``mutate`` to the clone, commit, push; on a lost race reset to the remote and apply it again."""
        for _ in range(self.max_retries):
            result = mutate()
            changed = self._commit(message)
            if crash_after_commit:
                self._crash(crash_after_commit)
            if not changed:
                return result
            if self._push():
                if crash_after_push:
                    self._crash(crash_after_push)
                return result
            self._reset_to_remote()
        raise StoreError(f"could not push after {self.max_retries} attempts")

    # ------------------------------------------------------------ reading
    @property
    def records(self) -> list[dict]:
        return list(self._records)

    @property
    def head(self) -> str:
        return self._records[-1]["hash"] if self._records else GENESIS

    def get(self, key) -> dict | None:
        return self._by_key.get(tuple(key))

    def of_type(self, type_: str) -> list[dict]:
        return [r for r in self._records if r["type"] == type_]

    def journal(self) -> list[dict]:
        return read_lines(self.workdir / JOURNAL)

    def raw_path(self, sha: str) -> Path:
        return self.workdir / "raw" / f"{sha}.bin"

    # ------------------------------------------------------------ appending (local; callers push)
    def _provenance(self, it: Intent) -> dict:
        return {"source": it.source, "retrieved_utc": it.retrieved_utc or _iso(self.clock()), "run_id": str(self.run_id),
                "run_attempt": int(self.run_attempt), "commit": self.commit}

    def _append_local(self, intents: list[Intent], torn: bool = False) -> dict:
        """Append to chain.jsonl in the clone. Returns counts. ``torn``: write half of the new lines, then half a
        line, then crash (the crash test of a write cut short)."""
        out = {"appended": 0, "duplicate": 0, "conflict": 0, "hashes": []}
        lines = []
        for it in intents:
            key = tuple(it.key)
            payload = _canon(it.payload)
            have = self._by_key.get(key)
            if have is not None:
                if content_hash(have["type"], have["key"], have["payload"]) == content_hash(it.type, key, payload):
                    out["duplicate"] += 1
                    out["hashes"].append(have["hash"])
                    continue
                out["conflict"] += 1
                rejected = content_hash(it.type, key, payload)
                ckey = ("conflict", *map(str, key), rejected[:16])
                if tuple(ckey) in self._by_key:
                    continue
                it = Intent("conflict", ckey, {"key": list(key), "existing_hash": have["hash"],
                                                "rejected_content_hash": rejected, "rejected_type": it.type},
                            source="runner")
                key, payload = tuple(ckey), _canon(it.payload)
            rec = {"seq": len(self._records) + 1, "ts_utc": _iso(self.clock()), "type": it.type, "key": list(key),
                   "nonce": self.nonce_fn(), "provenance": self._provenance(it), "payload": payload,
                   "prev_hash": self.head}
            rec["hash"] = record_hash(rec)
            self._records.append(rec)
            self._by_key[key] = rec
            lines.append(json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
            if it.type != "conflict":
                out["appended"] += 1
                out["hashes"].append(rec["hash"])
        path = self.workdir / CHAIN
        cut = len(lines) // 2 if torn and lines else None
        with path.open("a", encoding="utf-8") as f:
            for i, line in enumerate(lines):
                if cut is not None and i == cut:
                    f.write(line[: len(line) // 2])
                    f.flush()
                    raise SimulatedCrash("mid_chain_write")
                f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        return out

    def _journal_line(self, entry: dict) -> None:
        with (self.workdir / JOURNAL).open("a", encoding="utf-8") as f:
            f.write(json.dumps(_canon(entry), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")

    # ------------------------------------------------------------ the journalled write
    def write(self, intents: list[Intent], label: str, files: dict | None = None) -> dict:
        """Write ``intents`` (and content-addressed ``files``: relative path -> bytes) through the journal."""
        intents = [it if isinstance(it, Intent) else Intent.from_dict(it) for it in intents]
        body = [it.as_dict() for it in intents]
        entry = hashlib.sha256(S.canonical_bytes({"label": label, "intents": body,
                                                  "files": sorted((files or {}).keys())})).hexdigest()
        if any(j["entry"] == entry and j["state"] == "verified" for j in self.journal()):
            return {"entry": entry, "appended": 0, "duplicate": len(intents), "conflict": 0, "skipped": True}

        def pend():
            if not any(j["entry"] == entry for j in self.journal()):
                self._journal_line({"entry": entry, "state": "pending", "label": label, "run_id": str(self.run_id),
                                    "run_attempt": self.run_attempt, "ts_utc": _iso(self.clock()), "intents": body,
                                    "files": sorted((files or {}).keys())})
            for rel, data in (files or {}).items():
                p = self.workdir / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                if not p.exists():
                    p.write_bytes(data)
            if self.crash_at == "after_journal_local":
                raise SimulatedCrash("after_journal_local")

        self._transact(f"journal pending {entry[:12]} ({label})", pend, crash_after_push="after_journal_push")
        result = self._apply(entry, intents, label)
        self._verify_entry(entry, result["hashes"])
        return {"entry": entry, **{k: result[k] for k in ("appended", "duplicate", "conflict")}, "skipped": False}

    def _apply(self, entry: str, intents: list[Intent], label: str) -> dict:
        def commit_records():
            # the crash test cuts the first write that has at least two new lines
            torn = self.crash_at == "mid_chain_write" and sum(
                1 for it in intents if tuple(it.key) not in self._by_key) >= 2
            res = self._append_local(intents, torn=torn)
            if not any(j["entry"] == entry and j["state"] in ("committed", "verified") for j in self.journal()):
                self._journal_line({"entry": entry, "state": "committed", "ts_utc": _iso(self.clock()),
                                    "record_hashes": res["hashes"]})
            return res

        return self._transact(f"ledger {label}: records for {entry[:12]}", commit_records,
                              crash_after_commit="after_chain_commit_local", crash_after_push="after_chain_push")

    def _verify_entry(self, entry: str, hashes: list[str]) -> None:
        """Fetch the remote again and check the entry's records are there, then mark the entry verified."""
        self._git("fetch", "-q", "origin", BRANCH)
        remote = [json.loads(x) for x in self._git("show", f"origin/{BRANCH}:{CHAIN}").stdout.splitlines() if x.strip()]
        if verify_chain(remote):
            raise StoreError("the remote chain does not verify after the write")
        have = {r["hash"] for r in remote}
        if not set(hashes) <= have:
            raise StoreError("records written are missing from the remote")

        def mark():
            if not any(j["entry"] == entry and j["state"] == "verified" for j in self.journal()):
                self._journal_line({"entry": entry, "state": "verified", "ts_utc": _iso(self.clock())})

        self._transact(f"journal verified {entry[:12]}", mark)
        self._crash("after_verify")

    def unfinished(self) -> list[dict]:
        """Journal entries whose last state is not ``verified``, each with its pending intents."""
        state, pending = {}, {}
        for j in self.journal():
            state[j["entry"]] = j["state"]
            if j["state"] == "pending":
                pending[j["entry"]] = j
        return [pending[e] for e, s in state.items() if s != "verified" and e in pending]

    def reconcile(self) -> int:
        """Finish every entry a crash left unfinished. Returns how many were finished."""
        n = 0
        for j in self.unfinished():
            intents = [Intent.from_dict(d) for d in j["intents"]]
            missing = [f for f in j.get("files", []) if not (self.workdir / f).exists()]
            if missing:
                raise StoreError("a pending entry names files that never reached the ledger")
            res = self._apply(j["entry"], intents, j.get("label", "reconcile"))
            self._verify_entry(j["entry"], res["hashes"])
            n += 1
        return n

    # ------------------------------------------------------------ locks
    def active_locks(self) -> list[dict]:
        ended = {tuple(r["key"][1:3]) for r in self._records if r["type"] in ("unlock", "lock_broken")}
        return [r for r in self.of_type("lock") if tuple(r["key"][1:3]) not in ended]

    def acquire(self, ttl: timedelta = timedelta(minutes=75)) -> dict:
        """Take the run's lock: break expired locks, refuse a live one, and win the push race or stop."""
        me = ("lock", str(self.run_id), str(self.run_attempt))
        broken = 0
        for _ in range(self.max_retries):
            now = self.clock()
            intents = []
            for lk in self.active_locks():
                if tuple(lk["key"]) == me:
                    return {"status": "held", "broken": broken}
                earlier_attempt = lk["key"][1] == str(self.run_id) and int(lk["key"][2]) < int(self.run_attempt)
                live = datetime.fromisoformat(lk["payload"]["expires_utc"].replace("Z", "+00:00")) > now
                if live and not earlier_attempt:          # an earlier attempt of this run has ended: GitHub reruns after it
                    raise Locked("another run holds the ledger lock")
                intents.append(Intent("lock_broken", ("lock_broken", *lk["key"][1:3]),
                                      {"lock_hash": lk["hash"], "expired_utc": lk["payload"]["expires_utc"],
                                       "broken_by": [str(self.run_id), str(self.run_attempt)]}))
            intents.append(Intent("lock", me, {"expires_utc": _iso(now + ttl)}))
            self._append_local(intents)
            self._commit(f"lock {self.run_id}.{self.run_attempt}")
            if self._push():
                self._crash("after_lock")
                return {"status": "acquired", "broken": broken + len(intents) - 1}
            self._reset_to_remote()                        # someone else wrote first: look again
        raise Locked("could not take the lock")

    def release(self) -> None:
        self._crash("before_unlock")
        me = ("unlock", str(self.run_id), str(self.run_attempt))

        def unlock():
            if tuple(me) not in self._by_key:
                self._append_local([Intent("unlock", me, {})])

        self._transact(f"unlock {self.run_id}.{self.run_attempt}", unlock)

    # ------------------------------------------------------------ plain commits of private files
    def put_files(self, files: dict, message: str) -> None:
        """Commit private files that are not records (the run log, the heartbeat copy)."""
        def put():
            for rel, data in files.items():
                p = self.workdir / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)

        self._transact(message, put)

    # ------------------------------------------------------------ mirror
    def mirror(self, url: str | None) -> dict:
        """Push the ledger to the mirror by fast-forward only. A rejection is reported, never forced."""
        if not url:
            return {"status": "not_configured"}
        self._crash("mid_mirror")
        r = self._git("push", "-q", url, f"HEAD:refs/heads/{BRANCH}", check=False)
        if r.returncode != 0:
            return {"status": "rejected"}
        return {"status": "pushed"}

    def verify_mirror(self, url: str | None, scratch: Path) -> dict:
        if not url:
            return {"status": "not_configured"}
        scratch = Path(scratch)
        if scratch.exists():
            subprocess.run(["rm", "-rf", str(scratch)], check=True)
        r = subprocess.run(["git", "clone", "-q", "--branch", BRANCH, url, str(scratch)], capture_output=True, text=True)
        if r.returncode != 0:
            return {"status": "unreachable"}
        return verify_pair(self._records, read_lines(scratch / CHAIN))
