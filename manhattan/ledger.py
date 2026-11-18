"""The Manhattan ledger: a hash-chained, append-only record of every evaluation (ARCHITECTURE.md section 4).

Each record is one JSON line: ``seq`` (from 1), ``ts_utc``, ``type``, ``writer``, ``protocol`` (SHA-256 of the
protocol version in force), ``payload``, ``prev_hash`` (64 zeros for the first) and ``hash`` (SHA-256 of the
canonical form of all the other fields). A record is never edited; a mistake is fixed by a ``correction`` record.
Editing any line breaks every later hash. Replacing the whole file would not, so the head hash is anchored
outside the file (the public index, the batch tag, an external timestamp): ``verify`` takes the anchor.

Two ledgers of one design: the **full ledger** (private; holds outcomes) and the **public index**
(``data/manhattan/ledger/index.jsonl``; no outcome field is ever written to it).

Rerun detection (section 4.2). The key of an evaluation is ``(spec_hash, data_hash, window id)``:
unseen: ``evaluation`` (one look); seen with the same ``result_hash``: ``rerun`` (the same look); seen with a
different one: ``nondeterminism`` (both kept, the family suspended from tier changes); the same spec on a window
with a different ``data_hash``: a new ``evaluation`` flagged ``data_changed``, the first designated result
staying the result of record.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from . import spec as S

GENESIS = "0" * 64
TYPES = ("batch_freeze", "critic_review", "evaluation_started", "evaluation", "rerun", "nondeterminism",
         "screening_decision", "eprocess_update", "tier_change", "dormancy", "window_retired", "correction",
         "run_summary", "attempt_failed", "attempt_aborted")
FIELDS = ("seq", "ts_utc", "type", "writer", "protocol", "payload", "prev_hash")
ROLES = ("exploration", "reserve", "forward")
# Phase 4B: the identity every new registered attempt must carry, and the reason classes a terminal may give
IDENTITY_FIELDS = ("executable", "variant", "hypothesis", "family", "batch", "role", "channel", "designated",
                   "spec_hash", "data_hash", "window", "code_version")
ATTEMPT_SCHEMA = 2
TERMINAL_REASONS = ("execution_error", "data_unavailable", "interrupted", "cancelled", "validation_error")
COMPLETIONS = ("evaluation", "rerun", "nondeterminism")
# Written only through their own methods (start_evaluation, record_evaluation, end_attempt), never by append (S7 M5)
LIFECYCLE_TYPES = ("evaluation_started", *COMPLETIONS, "attempt_failed", "attempt_aborted")
PROTECTED_ROLES = ("reserve", "forward")
# keys that carry an outcome: never written to the public index
OUTCOME_KEYS = frozenset({"summary", "returns", "return_series", "result", "results", "p_value", "p", "e_value",
                          "wealth", "sharpe", "mean", "pnl", "t_stat", "tstat", "posterior", "pi", "outcome",
                          "n_obs"})


class LedgerError(RuntimeError):
    pass


def record_hash(rec: dict) -> str:
    return hashlib.sha256(S.canonical_bytes({k: rec[k] for k in FIELDS})).hexdigest()


def merkle_root(hashes: list[str]) -> str:
    """Merkle root of hex SHA-256 digests in the order given (the last one is paired with itself when a level is
    odd). The root of no hashes is 64 zeros."""
    if not hashes:
        return GENESIS
    level = [bytes.fromhex(h) for h in hashes]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


def evidential_weight(channel: str, role: str, designated: bool = False, reconstructed: bool = False) -> int:
    """ARCHITECTURE section 6.3: 1 only for a blind spec's designated reserve evaluation and for forward data
    dated after the spec's freeze that were recorded as they happened."""
    if role == "exploration":
        return 0
    if role == "reserve":
        return 1 if (channel == "blind" and designated and not reconstructed) else 0
    if role == "forward":
        return 0 if reconstructed else 1
    raise LedgerError(f"unknown role {role}")


def forward_observation_weight(*, eligible: bool, registration_weight: int, reconstructed: bool,
                               channel: str = "blind") -> int:
    """The weight of one recorded forward observation: the runner's existing rule, in one place so the runner and
    the reconciler apply the same function. An ineligible or weight-0 registration gives 0; otherwise
    ``evidential_weight`` for the forward role (0 when reconstructed)."""
    if not eligible or registration_weight == 0:
        return 0
    return evidential_weight(channel, "forward", False, reconstructed)


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify(path: Path, anchor: str | None = None) -> list[str]:
    """Problems found in a ledger file; preserve the legacy optional-anchor API."""
    try:
        snapshot = path.read_bytes()
    except FileNotFoundError:
        snapshot = b""
    return verify_snapshot(snapshot, anchor=anchor)[1]


def verify_snapshot(snapshot: bytes, anchor: str | None = None) -> tuple[list[dict], list[str]]:
    """Parse and verify one immutable byte snapshot; return its records and problems.

    Callers must process these returned records, rather than reopen the file.
    ``verify`` retains its historic optional-anchor API.
    """
    errs: list[str] = []
    prev = GENESIS
    recs = []
    try:
        lines = snapshot.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return [], ["ledger is not UTF-8"]
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            return recs, errs + [f"line {n}: not JSON"]
        if not isinstance(rec, dict):
            return recs, errs + [f"line {n}: record is not an object"]
        recs.append(rec)
        if rec.get("seq") != len(recs):
            return recs, errs + [f"line {n}: seq is {rec.get('seq')}, expected {len(recs)} (a record was removed, added or moved)"]
        if rec.get("prev_hash") != prev:
            return recs, errs + [f"record {rec['seq']}: prev_hash does not match the record before it"]
        if any(k not in rec for k in FIELDS) or rec.get("hash") != record_hash(rec):
            return recs, errs + [f"record {rec['seq']}: hash does not match its content (the record was edited)"]
        if rec["type"] not in TYPES:
            errs.append(f"record {rec['seq']}: unknown type {rec['type']}")
        prev = rec["hash"]
    if anchor is not None and prev != anchor:
        errs.append(f"head hash is {prev}, but the anchor says {anchor} (records are missing or the file was replaced)")
    return recs, errs


def require_code_identity(version) -> None:
    """A known Git commit and an engine or Git-tree content digest.

    Required for retries (4A-1a) and for every new registered attempt (``attempt_schema`` 2). Non-retry legacy
    evaluation APIs continue to accept their historical metadata. This validates identity syntax; authenticity
    of the running code is checked where the engine runs (``engine.evaluate``), not here.
    """
    def git_hash(value):
        return (isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) is not None
                and set(value) != {"0"})

    if not isinstance(version, dict) or not git_hash(version.get("commit")):
        raise LedgerError("retry requires a known code identity: Git commit and content digest")
    if not any(k in version for k in ("tree", "engine_sha256")):
        raise LedgerError("retry requires a known code identity: content digest missing")
    if ("tree" in version and not git_hash(version["tree"])) or (
            "engine_sha256" in version and (not isinstance(version["engine_sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", version["engine_sha256"]) is None
                or set(version["engine_sha256"]) == {"0"})):
        raise LedgerError("retry requires a known code identity: malformed content digest")


require_retry_code_identity = require_code_identity          # the 4A-1a name, kept for callers


def _sha(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_attempt_identity(p: dict) -> None:
    """Structural validation of a schema-2 attempt identity (Phase 4B). Never a statistical decision."""
    if not isinstance(p, dict):
        raise LedgerError("attempt identity must be an object")
    missing = [k for k in IDENTITY_FIELDS if k not in p]
    if missing:
        raise LedgerError("attempt identity is missing " + ", ".join(missing))
    w = p["window"]
    if (any(not isinstance(p[k], str) or not p[k].strip()
            for k in ("executable", "variant", "hypothesis", "family", "batch"))
            or p["role"] not in ROLES or p["channel"] not in S.CHANNELS or type(p["designated"]) is not bool
            or not _sha(p["spec_hash"]) or not _sha(p["data_hash"])
            or not isinstance(w, dict) or set(w) != {"id", "start", "end", "frequency"}
            or any(not isinstance(w[k], str) or not w[k].strip() for k in w)):
        raise LedgerError("malformed attempt identity")
    require_code_identity(p["code_version"])


def same_identity(start: dict, completion: dict) -> bool:
    """Whether a completion keeps every identity field its start registered (no role or window escalation).

    A ``data_changed`` evaluation is written with ``designated: false`` by the existing rule (the first designated
    result stays the result of record); that override is the only difference allowed."""
    for k in IDENTITY_FIELDS:
        if k not in start:
            continue
        if k == "designated" and completion.get("data_changed") is True and completion.get(k) is False:
            continue
        if completion.get(k) != start[k]:
            return False
    return True


def _designated_domain(p: dict) -> str | None:
    """The evaluation domain of a schema-2 designated reserve start, else None."""
    if p.get("attempt_schema") != ATTEMPT_SCHEMA or p.get("role") != "reserve" or p.get("designated") is not True:
        return None
    auth = p.get("authorization")
    windows = auth.get("windows") if isinstance(auth, dict) else None
    for w in windows if isinstance(windows, list) else []:
        if isinstance(w, dict) and w.get("purpose") == "evaluation" and isinstance(w.get("domain"), str):
            return w["domain"]
    return None


def _safe_key(p) -> tuple | None:
    try:
        k = (p["spec_hash"], p["data_hash"], p["window"]["id"])
        hash(k)
        return k
    except (KeyError, TypeError):
        return None


class Ledger:
    """One ledger file. ``append`` is the only way a record is written.

    Lifecycle queries are served from indexes kept in step with ``append`` (Phase 4B), so registering and completing
    attempts does not rescan the ledger. Their answers are those of the 4A-1a scans they replace."""

    public = False

    def __init__(self, path: Path, writer: str, protocol: str):
        self.path, self.writer, self.protocol = Path(path), writer, protocol
        errs = verify(self.path)
        if errs:
            raise LedgerError("the ledger does not verify: " + "; ".join(errs))
        self._recs = []
        self._starts: dict[str, dict] = {}            # attempt ID -> start record
        self._starts_by_key: dict[tuple, list] = {}
        self._terminated: set[str] = set()            # attempt IDs with a linked completion or terminal
        self._superseded: set[str] = set()
        self._evals_by_key: dict[tuple, list] = {}
        self._evals: list[dict] = []
        self._legacy_last: dict[tuple, int] = {}      # key -> seq of the latest unlinked completion
        self._designated: dict[tuple, list] = {}      # (batch, domain) -> designated reserve schema-2 starts
        for rec in read(self.path):
            self._index(rec)

    def _index(self, rec: dict) -> None:
        self._recs.append(rec)
        t, p = rec["type"], rec["payload"]
        if not isinstance(p, dict):
            return                                    # malformed: the reconciler reports it
        k = _safe_key(p)
        if t == "evaluation_started":
            self._starts[rec["hash"]] = rec
            if k is not None:
                self._starts_by_key.setdefault(k, []).append(rec)
            if isinstance(p.get("supersedes"), str):
                self._superseded.add(p["supersedes"])
            dom = _designated_domain(p)
            if dom is not None:
                self._designated.setdefault((p.get("batch"), dom), []).append(rec["hash"])
        elif t in COMPLETIONS:
            self._evals.append(rec)
            if k is not None:
                self._evals_by_key.setdefault(k, []).append(rec)
            if isinstance(p.get("attempt_id"), str):
                self._terminated.add(p["attempt_id"])
            elif "attempt_id" not in p and k is not None:
                self._legacy_last[k] = rec["seq"]
        elif t in ("attempt_failed", "attempt_aborted") and isinstance(p.get("attempt_id"), str):
            self._terminated.add(p["attempt_id"])

    # ---- reading
    def records(self, type_: str | None = None) -> list[dict]:
        return [r for r in self._recs if type_ is None or r["type"] == type_]

    @property
    def head(self) -> str:
        return self._recs[-1]["hash"] if self._recs else GENESIS

    def __len__(self) -> int:
        return len(self._recs)

    # ---- writing
    def append(self, type_: str, payload: dict, ts_utc: str | None = None) -> dict:
        """Append one record of a non-lifecycle type. Starts, completions and terminals are written only by
        ``start_evaluation``, ``record_evaluation`` and ``end_attempt``, which apply their rules (Phase 4B, S7 M5)."""
        if type_ in LIFECYCLE_TYPES:
            raise LedgerError(f"{type_} records are written by the lifecycle methods only")
        return self._append(type_, payload, ts_utc)

    def _append(self, type_: str, payload: dict, ts_utc: str | None = None) -> dict:
        """Append one record. The line is flushed and ``fsync``ed before this returns, so a registration that
        returned survives a crash of the process (Phase 4B)."""
        if type_ not in TYPES:
            raise LedgerError(f"unknown record type {type_}")
        rec = {"seq": len(self._recs) + 1,
               "ts_utc": ts_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "type": type_, "writer": self.writer, "protocol": self.protocol,
               "payload": json.loads(S.canonical_bytes(payload)), "prev_hash": self.head}
        rec["hash"] = record_hash(rec)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        self._index(rec)
        return rec

    def correction(self, target_seq: int, fields: dict, reason: str) -> dict:
        """Record that fields of an earlier record were wrong. ``fields`` maps each to {"old": ..., "new": ...};
        the earlier record stays as it is."""
        if not 1 <= target_seq <= len(self._recs):
            raise LedgerError("a correction must name an existing record")
        if not reason or not reason.strip():
            raise LedgerError("a correction needs a reason")
        if not fields or any(set(v) != {"old", "new"} for v in fields.values()):
            raise LedgerError("a correction lists each field with its old and new value")
        target = self._recs[target_seq - 1]
        return self.append("correction", {"target_seq": target_seq, "target_hash": target["hash"],
                                          "fields": fields, "reason": reason})

    # ---- evaluations
    @staticmethod
    def key(payload: dict) -> tuple[str, str, str]:
        return payload["spec_hash"], payload["data_hash"], payload["window"]["id"]

    def _evaluations(self) -> list[dict]:
        return list(self._evals)

    def start_evaluation(self, payload: dict, *, supersedes: str | None = None) -> dict:
        """Register an execution; the returned start record's hash is its attempt ID.

        Retries name an unfinished start and preserve it in the denominator. A payload with ``attempt_schema: 2``
        (written by ``manhattan.access``) must carry the full identity of ``IDENTITY_FIELDS`` with a known code
        identity, and keeps its ``kind`` and ``authorization``. This API alone does not authorize a PIT read:
        ``manhattan.access.register_evaluation`` validates the declared windows first.
        """
        fields = ("executable", "family", "batch", "spec_hash", "data_hash", "window")
        if payload.get("attempt_schema") == ATTEMPT_SCHEMA:
            validate_attempt_identity(payload)
            if not isinstance(payload.get("kind"), str) or not isinstance(payload.get("authorization"), dict):
                raise LedgerError("a registered attempt declares its kind and authorization")
            p = {k: payload[k] for k in (*IDENTITY_FIELDS, "attempt_schema", "kind", "authorization")}
        elif "attempt_schema" in payload:
            raise LedgerError("unknown attempt schema")
        else:
            p = {k: payload[k] for k in fields}
            p.update({k: payload[k] for k in ("variant", "hypothesis", "role", "channel", "designated",
                                              "code_version") if k in payload})
        if supersedes is not None:
            old = self.active_attempt(supersedes)
            require_code_identity(p.get("code_version"))
            require_code_identity(old["payload"].get("code_version"))
            if old["payload"] != p:
                # Only the retry link itself may differ across repeated interruptions.
                prior = {k: v for k, v in old["payload"].items() if k != "supersedes"}
                if prior != p:
                    raise LedgerError("retry identity differs from interrupted attempt")
            p["supersedes"] = supersedes
        return self._append("evaluation_started", p)

    def active_attempt(self, attempt_id: str) -> dict:
        start = self._starts.get(attempt_id) if isinstance(attempt_id, str) else None
        if start is None or not self._unfinished_one(start):
            raise LedgerError("attempt is not registered and unfinished")
        if attempt_id in self._superseded:
            raise LedgerError("attempt has been superseded")
        return start

    def _unfinished_one(self, r: dict) -> bool:
        """The 4A-1a ``unfinished`` predicate for one start."""
        if r["hash"] in self._terminated:
            return False
        if r["hash"] in self._superseded:
            return True
        k = _safe_key(r["payload"])
        return k is None or self._legacy_last.get(k, 0) < r["seq"]

    def end_attempt(self, attempt_id: str, *, status: str, reason: str, data_read: bool | None = None) -> dict:
        """Safe classified failure/abortion only; never exception text or outcomes.

        ``data_read`` (Phase 4B) says whether any value was read through the attempt's windows; registered
        (schema-2) attempts must state it, legacy attempts may not."""
        if status not in ("failed", "aborted"):
            raise LedgerError("terminal status must be failed or aborted")
        if reason not in TERMINAL_REASONS:
            raise LedgerError("unknown attempt reason classification")
        start = self.active_attempt(attempt_id)
        payload = {"attempt_id": attempt_id, "reason": reason}
        if start["payload"].get("attempt_schema") == ATTEMPT_SCHEMA:
            if type(data_read) is not bool:
                raise LedgerError("a registered attempt's terminal states whether data were read")
            payload["data_read"] = data_read
        elif data_read is not None:
            raise LedgerError("legacy attempts carry no data_read flag")
        return self._append("attempt_" + status, payload)

    def record_evaluation(self, *, executable: str, variant: str, hypothesis: str, family: str, batch: str,
                          channel: str, role: str, window: dict, designated: bool, spec_hash: str, data_hash: str,
                          code_version: dict, result_hash: str, n_obs: int, summary: dict, seed: int,
                          reconstructed: bool = False, attempt_id: str | None = None, proof=None) -> dict:
        """Record one evaluation, deciding by its key whether it is a new look, a rerun or a nondeterminism.

        A reserve or forward completion (owner decision D-5, S7 M5) needs ``proof``: the one-use
        ``access.CompletionProof`` that only ``engine.evaluate`` obtains, from the active attempt that read its
        window, for this result. An attempt ID alone never writes a protected result."""
        if role not in ROLES or channel not in S.CHANNELS:
            raise LedgerError("role must be exploration, reserve or forward; channel blind or adaptive")
        if role in PROTECTED_ROLES:
            from manhattan import access
            start = self._starts.get(attempt_id) if isinstance(attempt_id, str) else None
            if start is None or start["payload"].get("attempt_schema") != ATTEMPT_SCHEMA:
                raise LedgerError("a reserve or forward completion needs a registered (schema 2) attempt")
            access.verify_completion(proof, attempt_id=attempt_id, result_hash=result_hash, ledger=self)
        payload = {"executable": executable, "variant": variant, "hypothesis": hypothesis, "family": family,
                   "batch": batch, "channel": channel, "role": role, "window": window, "designated": bool(designated),
                   "spec_hash": spec_hash, "data_hash": data_hash, "code_version": code_version,
                   "result_hash": result_hash, "n_obs": n_obs, "summary": summary, "seed": seed,
                   "reconstructed": bool(reconstructed),
                   "evidential_weight": evidential_weight(channel, role, designated, reconstructed)}
        if attempt_id is None:
            candidates = [r for r in self._starts_by_key.get(self.key(payload), [])
                          if self._unfinished_one(r) and r["hash"] not in self._superseded]
            if len(candidates) > 1:
                raise LedgerError("ambiguous attempt: supply attempt_id")
            if candidates:
                if candidates[0]["payload"].get("attempt_schema") == ATTEMPT_SCHEMA:
                    raise LedgerError("a registered attempt completes only through its own attempt_id")
                attempt_id = candidates[0]["hash"]
        if attempt_id is not None:
            start = self.active_attempt(attempt_id)
            if not same_identity(start["payload"], payload):
                raise LedgerError("completion identity differs from attempt")
            payload["attempt_id"] = attempt_id
        same_key = self._evals_by_key.get(self.key(payload), [])
        if same_key:
            first = same_key[0]
            if all(r["payload"]["result_hash"] == result_hash for r in same_key):
                payload.update(evidential_weight=0, first_seq=first["seq"])
                return self._append("rerun", payload)
            payload.update(evidential_weight=0, first_seq=first["seq"], first_result_hash=first["payload"]["result_hash"])
            return self._append("nondeterminism", payload)
        earlier = [r for r in self._evals if r["type"] == "evaluation" and r["payload"]["spec_hash"] == spec_hash
                   and r["payload"]["window"]["id"] == window["id"]]
        if earlier:
            of_record = next((r for r in earlier if r["payload"]["designated"]), earlier[0])
            payload.update(data_changed=True, designated=False, evidential_weight=0, result_of_record_seq=of_record["seq"])
        return self._append("evaluation", payload)

    def designated_reserve_starts(self, batch: str, domain: str) -> list[str]:
        """Attempt IDs of the registered designated reserve evaluations of (batch, domain) (D-6)."""
        return list(self._designated.get((batch, domain), []))

    def is_superseded(self, attempt_id: str) -> bool:
        return attempt_id in self._superseded

    def looks(self) -> int:
        """Distinct evaluations (reruns are the same look and count once)."""
        return len(self._evals_by_key)

    def unfinished(self) -> list[dict]:
        return [r for r in self._starts.values() if self._unfinished_one(r)]

    def suspended_families(self) -> set[str]:
        """Families with a nondeterminism on record: no tier change until the cause is found."""
        return {r["payload"]["family"] for r in self.records("nondeterminism")}

    def result_of_record(self, spec_hash: str, window_id: str) -> dict | None:
        """The first designated evaluation of a spec on a window, which later data revisions never replace."""
        for r in self.records("evaluation"):
            p = r["payload"]
            if p["spec_hash"] == spec_hash and p["window"]["id"] == window_id and p["designated"]:
                return r
        return None

    def run_summary_payload(self) -> dict:
        """What the public index stores about this ledger at the end of a run: no outcome."""
        return {"ledger_records": len(self._recs), "ledger_head": self.head,
                "merkle_root": merkle_root([r["hash"] for r in self._recs])}


def recover_torn_tail(path: Path) -> dict:
    """Crash recovery for a write cut short (Phase 4B). Never removes a complete record.

    Only a final fragment that has no newline and does not parse as a JSON object is moved, byte for byte, to
    ``<name>.torn-<sha256>`` beside the ledger; a complete final record that lost only its newline gets the newline.
    Anything else (a damaged record in the middle, an edited record) is not a torn tail and is refused: ``verify``
    reports it and the ledger stays unopenable. Returns what was done."""
    path = Path(path)
    data = path.read_bytes() if path.exists() else b""
    if not data or data.endswith(b"\n"):
        return {"status": "clean"}
    cut = data.rfind(b"\n") + 1
    head, tail = data[:cut], data[cut:]
    try:
        rec = json.loads(tail.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        rec = None
    if isinstance(rec, dict):
        if verify_snapshot(data + b"\n")[1]:
            raise LedgerError("the final record is complete JSON but does not verify: not a torn write")
        with path.open("ab") as f:
            f.write(b"\n")
            f.flush()
            os.fsync(f.fileno())
        return {"status": "newline_restored"}
    head_recs, head_errs = verify_snapshot(head)
    if head_errs:
        raise LedgerError("the ledger before the torn tail does not verify: not a torn write")
    # A torn append is a prefix of exactly one record line, which (sort_keys) begins with '{"hash":"'. A fragment
    # holding a second record start, or naming another sequence number, is damage, not a torn write.
    lead = b'{"hash":"'
    seq = re.search(rb'"seq":(\d+)[,}]', tail)
    if not (tail.startswith(lead) or lead.startswith(tail)) or tail.find(lead, 1) != -1 or \
            (seq is not None and int(seq.group(1)) != len(head_recs) + 1):
        raise LedgerError("the final fragment is not one partial record: not a torn write")
    digest = hashlib.sha256(tail).hexdigest()
    side = path.with_name(f"{path.name}.torn-{digest}")
    side.write_bytes(tail)
    with path.open("r+b") as f:
        f.truncate(cut)
        f.flush()
        os.fsync(f.fileno())
    return {"status": "torn_tail_quarantined", "bytes": len(tail), "quarantine": side.name}


def outcome_keys_in(obj, path: str = "") -> list[str]:
    """Paths of keys that carry an outcome, anywhere inside ``obj``."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{path}.{k}" if path else str(k)
            if str(k).lower() in OUTCOME_KEYS:
                found.append(here)
            found += outcome_keys_in(v, here)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            found += outcome_keys_in(v, f"{path}[{i}]")
    return found


class PublicIndex(Ledger):
    """The public index: the same chain, and a refusal of anything that carries an outcome."""

    public = True
    ALLOWED = ("batch_freeze", "run_summary", "screening_decision", "tier_change", "correction", "window_retired")

    def append(self, type_: str, payload: dict, ts_utc: str | None = None) -> dict:
        if type_ not in self.ALLOWED:
            raise LedgerError(f"the public index does not hold {type_} records")
        bad = outcome_keys_in(payload)
        if bad:
            raise LedgerError("the public index never holds an outcome: " + ", ".join(bad))
        return super().append(type_, payload, ts_utc)
