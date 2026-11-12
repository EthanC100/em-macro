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
from datetime import datetime, timezone
from pathlib import Path

from . import spec as S

GENESIS = "0" * 64
TYPES = ("batch_freeze", "critic_review", "evaluation_started", "evaluation", "rerun", "nondeterminism",
         "screening_decision", "eprocess_update", "tier_change", "dormancy", "window_retired", "correction",
         "run_summary")
FIELDS = ("seq", "ts_utc", "type", "writer", "protocol", "payload", "prev_hash")
ROLES = ("exploration", "reserve", "forward")
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
        return 1 if (channel == "blind" and designated) else 0
    if role == "forward":
        return 0 if reconstructed else 1
    raise LedgerError(f"unknown role {role}")


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify(path: Path, anchor: str | None = None) -> list[str]:
    """Problems found in a ledger file (empty when the chain is intact and, if given, ends at ``anchor``)."""
    errs: list[str] = []
    prev = GENESIS
    recs = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines() if path.exists() else [], 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            return errs + [f"line {n}: not JSON"]
        recs.append(rec)
        if rec.get("seq") != len(recs):
            return errs + [f"line {n}: seq is {rec.get('seq')}, expected {len(recs)} (a record was removed, added or moved)"]
        if rec.get("prev_hash") != prev:
            return errs + [f"record {rec['seq']}: prev_hash does not match the record before it"]
        if any(k not in rec for k in FIELDS) or rec.get("hash") != record_hash(rec):
            return errs + [f"record {rec['seq']}: hash does not match its content (the record was edited)"]
        if rec["type"] not in TYPES:
            errs.append(f"record {rec['seq']}: unknown type {rec['type']}")
        prev = rec["hash"]
    if anchor is not None and prev != anchor:
        errs.append(f"head hash is {prev}, but the anchor says {anchor} (records are missing or the file was replaced)")
    return errs


class Ledger:
    """One ledger file. ``append`` is the only way a record is written."""

    public = False

    def __init__(self, path: Path, writer: str, protocol: str):
        self.path, self.writer, self.protocol = Path(path), writer, protocol
        errs = verify(self.path)
        if errs:
            raise LedgerError("the ledger does not verify: " + "; ".join(errs))
        self._recs = read(self.path)

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
        if type_ not in TYPES:
            raise LedgerError(f"unknown record type {type_}")
        rec = {"seq": len(self._recs) + 1,
               "ts_utc": ts_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "type": type_, "writer": self.writer, "protocol": self.protocol,
               "payload": json.loads(S.canonical_bytes(payload)), "prev_hash": self.head}
        rec["hash"] = record_hash(rec)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
        self._recs.append(rec)
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
        return [r for r in self._recs if r["type"] in ("evaluation", "rerun", "nondeterminism")]

    def start_evaluation(self, payload: dict) -> dict:
        """Written before a designated evaluation runs; a start with no finish is reported by ``unfinished``."""
        return self.append("evaluation_started", {k: payload[k] for k in
                                                  ("executable", "family", "batch", "spec_hash", "data_hash", "window")})

    def record_evaluation(self, *, executable: str, variant: str, hypothesis: str, family: str, batch: str,
                          channel: str, role: str, window: dict, designated: bool, spec_hash: str, data_hash: str,
                          code_version: dict, result_hash: str, n_obs: int, summary: dict, seed: int,
                          reconstructed: bool = False) -> dict:
        """Record one evaluation, deciding by its key whether it is a new look, a rerun or a nondeterminism."""
        if role not in ROLES or channel not in S.CHANNELS:
            raise LedgerError("role must be exploration, reserve or forward; channel blind or adaptive")
        payload = {"executable": executable, "variant": variant, "hypothesis": hypothesis, "family": family,
                   "batch": batch, "channel": channel, "role": role, "window": window, "designated": bool(designated),
                   "spec_hash": spec_hash, "data_hash": data_hash, "code_version": code_version,
                   "result_hash": result_hash, "n_obs": n_obs, "summary": summary, "seed": seed,
                   "evidential_weight": evidential_weight(channel, role, designated, reconstructed)}
        same_key = [r for r in self._evaluations() if self.key(r["payload"]) == self.key(payload)]
        if same_key:
            first = same_key[0]
            if all(r["payload"]["result_hash"] == result_hash for r in same_key):
                payload.update(evidential_weight=0, first_seq=first["seq"])
                return self.append("rerun", payload)
            payload.update(evidential_weight=0, first_seq=first["seq"], first_result_hash=first["payload"]["result_hash"])
            return self.append("nondeterminism", payload)
        earlier = [r for r in self._evaluations() if r["type"] == "evaluation" and r["payload"]["spec_hash"] == spec_hash
                   and r["payload"]["window"]["id"] == window["id"]]
        if earlier:
            of_record = next((r for r in earlier if r["payload"]["designated"]), earlier[0])
            payload.update(data_changed=True, designated=False, evidential_weight=0, result_of_record_seq=of_record["seq"])
        return self.append("evaluation", payload)

    def looks(self) -> int:
        """Distinct evaluations (reruns are the same look and count once)."""
        return len({self.key(r["payload"]) for r in self._evaluations()})

    def unfinished(self) -> list[dict]:
        done = {self.key(r["payload"]) for r in self._evaluations()}
        return [r for r in self.records("evaluation_started") if self.key(r["payload"]) not in done]

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
