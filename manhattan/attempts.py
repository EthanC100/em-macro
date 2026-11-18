"""Attempt accounting audits.

``reconcile_lifecycle`` (Phase 4A-1a): strict lifecycle-only accounting of one Manhattan ledger. It does not
reconcile data access and always answers ``access_reconciled: false``. Legacy unlinked evaluations fail it.

``reconcile`` (Phase 4B, docs/manhattan/BINDING_ACCOUNTING.md section 9): both authoritative stores (the Manhattan
``Ledger`` and the operational ``Store``), each audited from an immutable snapshot up to an independently retained
anchor ``{"records": n, "head": hash}`` that marks an authenticated batch boundary. Integrity failures raise;
accounting failures are reported as violation codes with store and sequence numbers only, never values.
``access_reconciled`` is true only when every supported guarantee holds for the stores supplied.

An independently retained head anchor is required to detect suffix deletion.
"""
import json
import re
from pathlib import Path

from . import ledger as L, spec as S


def reconcile_lifecycle(path: Path, *, anchor: str) -> dict:
    if not isinstance(anchor, str) or re.fullmatch(r"[0-9a-f]{64}", anchor) is None:
        raise L.LedgerError("lifecycle reconciliation requires a valid external SHA-256 anchor")
    try:
        snapshot = Path(path).read_bytes()
    except OSError as exc:
        raise L.LedgerError("cannot read ledger snapshot") from exc
    records, errors = L.verify_snapshot(snapshot, anchor=anchor)
    if errors:
        raise L.LedgerError('; '.join(errors))
    starts, terminal, superseded = {}, {}, set()
    retries = 0
    for r in records:
        p, kind = r['payload'], r['type']
        if not isinstance(p, dict):
            raise L.LedgerError('lifecycle payload must be an object')
        if kind == 'evaluation_started':
            prior = p.get('supersedes')
            if prior is not None:
                if not isinstance(prior, str) or prior not in starts or prior in terminal or prior in superseded:
                    raise L.LedgerError('invalid retry relationship')
                identity = lambda x: {k: v for k, v in x.items() if k != 'supersedes'}
                L.require_code_identity(p.get("code_version"))
                L.require_retry_code_identity(starts[prior].get("code_version"))
                if identity(p) != identity(starts[prior]):
                    raise L.LedgerError('contradictory retry identity')
                superseded.add(prior)
                retries += 1
            starts[r['hash']] = p
        elif kind in ('evaluation', 'rerun', 'nondeterminism', 'attempt_failed', 'attempt_aborted'):
            aid = p.get('attempt_id')
            if not isinstance(aid, str) or aid not in starts or aid in superseded:
                raise L.LedgerError('terminal record without an active registered attempt')
            if aid in terminal:
                raise L.LedgerError('duplicate or contradictory terminal status')
            if kind.startswith('attempt_'):
                if not _valid_ledger_terminal(p, starts[aid]):
                    raise L.LedgerError('invalid terminal metadata')
                terminal[aid] = kind.removeprefix('attempt_')
            else:
                _validate_completion(p)
                if not L.same_identity(starts[aid], p):
                    raise L.LedgerError('contradictory completion identity')
                terminal[aid] = 'completed'
    counts = {status: sum(v == status for v in terminal.values())
              for status in ('completed', 'failed', 'aborted')}
    unfinished = sorted(set(starts) - set(terminal))
    return {'registered': len(starts), **counts, 'unfinished': len(unfinished),
            'unfinished_attempts': unfinished, 'retries': retries,
            'distinct_specifications': len({p['spec_hash'] for p in starts.values()}),
            'access_reconciled': False}


def _validate_completion(p: dict) -> None:
    """Validate record structure only; never decide or publish a statistical outcome."""
    strings = ("executable", "variant", "hypothesis", "family", "batch", "spec_hash", "data_hash", "result_hash")
    required = set(strings) | {"channel", "role", "window", "designated", "code_version", "n_obs",
                               "summary", "seed", "reconstructed", "evidential_weight", "attempt_id"}
    if not required <= p.keys():
        raise L.LedgerError("incomplete evaluation completion schema")
    window = p["window"]
    if (any(not isinstance(p[k], str) or not p[k].strip() for k in strings)
            or any(re.fullmatch(r"[0-9a-f]{64}", p[k]) is None
                   for k in ("spec_hash", "data_hash", "result_hash"))
            or p["role"] not in L.ROLES or p["channel"] not in S.CHANNELS
            or not isinstance(window, dict)
            or any(not isinstance(window.get(k), str) or not window[k].strip()
                   for k in ("id", "start", "end", "frequency"))
            or type(p["designated"]) is not bool or type(p["reconstructed"]) is not bool
            or not isinstance(p["code_version"], dict) or not p["code_version"]
            or type(p["n_obs"]) is not int or p["n_obs"] < 0
            or type(p["seed"]) is not int or not isinstance(p["summary"], dict)
            or type(p["evidential_weight"]) is not int or p["evidential_weight"] not in (0, 1)):
        raise L.LedgerError("malformed evaluation completion schema")


def _valid_ledger_terminal(p: dict, start: dict) -> bool:
    """Legacy terminals hold the attempt and a reason class; schema-2 terminals also say whether data were read."""
    keys = {"attempt_id", "reason"}
    if start.get("attempt_schema") == L.ATTEMPT_SCHEMA:
        keys = keys | {"data_read"}
        if type(p.get("data_read")) is not bool:
            return False
    return set(p) == keys and p["reason"] in L.TERMINAL_REASONS


# ==================================================================== Phase 4B: both stores

class ReconciliationError(L.LedgerError):
    """A store's history cannot be trusted (broken chain, anchor mismatch, unreadable snapshot)."""


PROTECTED = ("reserve", "forward")
STORE_KINDS = ("screening", "forward_observation")
LIMITATIONS = (
    "covers Manhattan code paths only (ARCHITECTURE section 8): reads outside Manhattan code leave no record",
    "in-process enforcement is structural, not a sandbox: deliberate use of private names can bypass it",
    "anchors authenticate the boundary only if they were retained independently of the stores' writer",
    "reserve tokens are recorded, not re-verified; the ops code identity digest covers manhattan/engine only",
    "exploratory (open) access is not logged by design",
)


def _anchor(anchor, name: str) -> tuple[int, str]:
    if (not isinstance(anchor, dict) or set(anchor) != {"records", "head"} or type(anchor["records"]) is not int
            or anchor["records"] < 0 or not isinstance(anchor["head"], str)
            or re.fullmatch(r"[0-9a-f]{64}", anchor["head"]) is None):
        raise ReconciliationError(f"{name} reconciliation requires an anchor {{records, head}} retained outside it")
    return anchor["records"], anchor["head"]


def _prefix(records: list, anchor: tuple, name: str) -> list:
    n, head = anchor
    if n > len(records) or (records[n - 1]["hash"] if n else L.GENESIS) != head:
        raise ReconciliationError(f"the {name} does not reach its anchor (records deleted, replaced or rewritten)")
    return records[:n]


def _read(path, name: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise ReconciliationError(f"cannot read the {name} snapshot") from exc


class _Audit:
    def __init__(self, batch):
        self.batch = batch
        self.violations: list[dict] = []
        self.counts = {"registered_executions": 0, "completed": 0, "failed": 0, "aborted": 0, "unfinished": 0,
                       "superseded_interrupted": 0, "retries": 0}
        self.read = {"failed_read": 0, "failed_unread": 0, "aborted_read": 0, "aborted_unread": 0,
                     "aborted_unknown": 0}
        self.specs, self.keys = set(), set()
        self.legacy = {"starts": 0, "unlinked_exploration": 0, "protected_records": 0}
        self.observations = 0
        self.designated: dict[str, int] = {}

    def v(self, code: str, store: str, seq) -> None:
        self.violations.append({"code": code, "store": store, "seq": seq})

    def scoped(self, identity) -> bool:
        return self.batch is None or (isinstance(identity, dict) and identity.get("batch") == self.batch)

    def ended(self, status: str, data_read) -> None:
        self.counts[status] += 1
        if status in ("failed", "aborted"):
            key = f"{status}_{'unknown' if data_read is None else ('read' if data_read else 'unread')}"
            if key in self.read:
                self.read[key] += 1
            else:                                       # a failed attempt with unknown reads counts as read
                self.read[f"{status}_read"] += 1


def _ledger_pass(records: list, audit: _Audit) -> set:
    from . import access as A
    starts, terminal, superseded = {}, {}, set()
    for r in records:
        seq, kind, p = r["seq"], r["type"], r["payload"]
        if not isinstance(p, dict):
            audit.v("malformed_record", "ledger", seq)
            continue
        if kind == "evaluation_started":
            schema2 = p.get("attempt_schema") == L.ATTEMPT_SCHEMA
            if schema2:
                try:
                    ident = {k: p[k] for k in L.IDENTITY_FIELDS}
                    L.validate_attempt_identity(ident)
                    if p.get("kind") != "engine_evaluation":
                        raise A.AccessError("kind")
                    A.check_recorded("engine_evaluation", ident, p.get("authorization"))
                except (KeyError, L.LedgerError, PermissionError):
                    audit.v("invalid_identity_or_authorization", "ledger", seq)
            elif "attempt_schema" in p:
                audit.v("unknown_attempt_schema", "ledger", seq)
            else:
                audit.legacy["starts"] += 1
                if p.get("role") in PROTECTED or "role" not in p:
                    audit.legacy["protected_records"] += 1
            prior = p.get("supersedes")
            if prior is not None:
                ok = isinstance(prior, str) and prior in starts and prior not in terminal and prior not in superseded
                if ok:
                    try:
                        L.require_code_identity(p.get("code_version"))
                        L.require_code_identity(starts[prior][1].get("code_version"))
                    except L.LedgerError:
                        ok = False
                    ok = ok and {k: v for k, v in p.items() if k != "supersedes"} == \
                        {k: v for k, v in starts[prior][1].items() if k != "supersedes"}
                if not ok:
                    audit.v("invalid_retry", "ledger", seq)
                else:
                    superseded.add(prior)
                    if audit.scoped(p):
                        audit.counts["retries"] += 1
            starts[r["hash"]] = (seq, p)
            if audit.scoped(p):
                audit.counts["registered_executions"] += 1
                if isinstance(p.get("spec_hash"), str):
                    audit.specs.add(p["spec_hash"])
        elif kind in L.COMPLETIONS:
            aid = p.get("attempt_id")
            if aid is None:
                if p.get("role") in PROTECTED:
                    audit.v("unregistered_protected_evaluation", "ledger", seq)
                else:
                    audit.legacy["unlinked_exploration"] += 1
                continue
            if not isinstance(aid, str) or aid not in starts or aid in superseded:
                audit.v("terminal_without_active_attempt", "ledger", seq)
                continue
            if aid in terminal:
                audit.v("duplicate_or_contradictory_terminal", "ledger", seq)
                continue
            start = starts[aid][1]
            terminal[aid] = "completed"
            try:
                _validate_completion(p)
            except L.LedgerError:
                audit.v("malformed_completion", "ledger", seq)
                continue
            if not L.same_identity(start, p):
                audit.v("identity_or_role_escalation", "ledger", seq)
            expected = 0 if (kind != "evaluation" or p.get("data_changed")) else \
                L.evidential_weight(p["channel"], p["role"], p["designated"], p["reconstructed"])
            if p["evidential_weight"] != expected:
                audit.v("evidential_weight_mismatch", "ledger", seq)
            if start.get("attempt_schema") != L.ATTEMPT_SCHEMA and p["role"] in PROTECTED:
                audit.legacy["protected_records"] += 1
            if audit.scoped(start):
                audit.ended("completed", True)
                audit.keys.add(("ledger", p["spec_hash"], p["data_hash"], p["window"]["id"]))
                if kind == "evaluation" and p["role"] == "reserve" and p["designated"] and not p.get("data_changed"):
                    auth = start.get("authorization") if isinstance(start.get("authorization"), dict) else {}
                    dom = next((w.get("domain") for w in auth.get("windows", []) if isinstance(w, dict)
                                and w.get("purpose") == "evaluation"), "unknown")
                    k = f"{p['batch']}|{dom}"
                    audit.designated[k] = audit.designated.get(k, 0) + 1
        elif kind in ("attempt_failed", "attempt_aborted"):
            aid = p.get("attempt_id")
            if not isinstance(aid, str) or aid not in starts or aid in superseded or aid in terminal:
                audit.v("terminal_without_active_attempt", "ledger", seq)
                continue
            status = kind.removeprefix("attempt_")
            terminal[aid] = status
            if not _valid_ledger_terminal(p, starts[aid][1]):
                audit.v("invalid_terminal_metadata", "ledger", seq)
            elif audit.scoped(starts[aid][1]):
                audit.ended(status, p.get("data_read", True))
    for aid, (seq, p) in starts.items():
        if aid in terminal or not audit.scoped(p):
            continue
        if aid in superseded:
            audit.counts["superseded_interrupted"] += 1
        else:
            audit.counts["unfinished"] += 1
            audit.v("missing_terminal", "ledger", seq)
    return set(starts)


def _store_pass(records: list, audit: _Audit) -> set:
    from . import access as A
    by_key = {tuple(r["key"]): r for r in records}
    epoch = by_key.get(("accounting_epoch", str(L.ATTEMPT_SCHEMA)))
    epoch_seq = epoch["seq"] if epoch else None
    starts, terminal, retried, linked = {}, {}, set(), {}
    active_by_identity: dict[bytes, str] = {}
    for r in records:
        seq, kind, p, key = r["seq"], r["type"], r["payload"], tuple(r["key"])
        if kind == A.STORE_START:
            aid = key[1] if len(key) == 2 else None
            ok = isinstance(p, dict) and isinstance(aid, str) and A.store_attempt_id(p) == aid
            if not ok:
                audit.v("attempt_id_mismatch", "store", seq)
                continue
            try:
                if p.get("attempt_schema") != L.ATTEMPT_SCHEMA or p.get("kind") not in STORE_KINDS:
                    raise A.AccessError("schema")
                L.validate_attempt_identity(p["identity"])
                A.check_recorded(p["kind"], p["identity"], p["authorization"])
                # The run is bound into the attempt ID. The record's provenance may name a later run instead:
                # the one whose journal recovery finished this write.
                run = p["run"]
                if not isinstance(run, dict) or set(run) != {"run_id", "run_attempt"} or \
                        not isinstance(run["run_id"], str) or type(run["run_attempt"]) is not int:
                    raise A.AccessError("run")
                if not isinstance(p["subject"], dict) or set(p["subject"]) != set(A.SUBJECT_KEYS[p["kind"]]):
                    raise A.AccessError("subject")
                if not isinstance(p.get("nonce"), str) or re.fullmatch(r"[0-9a-f]{32}", p["nonce"]) is None:
                    raise A.AccessError("nonce")
            except (KeyError, TypeError, L.LedgerError, PermissionError):
                audit.v("invalid_identity_or_authorization", "store", seq)
                continue
            ident_key = S.canonical_bytes(A.comparable(p))
            prior = p.get("retry_of")
            if prior is not None:
                t = terminal.get(prior)
                ok = (isinstance(prior, str) and prior in starts and prior not in retried and t is not None
                      and t[0] == "aborted" and t[1] == "interrupted"
                      and S.canonical_bytes(A.comparable(starts[prior][1])) == ident_key)
                if not ok:
                    audit.v("invalid_retry", "store", seq)
                else:
                    retried.add(prior)
                    if audit.scoped(p["identity"]):
                        audit.counts["retries"] += 1
            other = active_by_identity.get(ident_key)
            if other is not None and other not in terminal:
                audit.v("concurrent_execution_without_recovery", "store", seq)
            active_by_identity[ident_key] = aid
            starts[aid] = (seq, p)
            if audit.scoped(p["identity"]):
                audit.counts["registered_executions"] += 1
                audit.specs.add(p["identity"]["spec_hash"])
        elif kind in A.STORE_TERMINAL_TYPES.values():
            aid = key[1] if len(key) == 2 and key[0] == A.STORE_TERMINAL else None
            if aid not in starts or not isinstance(p, dict) or p.get("attempt_id") != aid:
                audit.v("terminal_without_attempt", "store", seq)
                continue
            status = kind.removeprefix("attempt_")
            sseq, sp = starts[aid]
            valid = (set(p) == {"attempt_id", "status", "reason", "data_read", "results"} and p["status"] == status
                     and (p["data_read"] is None or type(p["data_read"]) is bool)
                     and isinstance(p["results"], list))
            if valid and status == "completed":
                valid = p["reason"] is None and p["data_read"] is True
            elif valid:
                valid = p["reason"] in L.TERMINAL_REASONS and p["results"] == [] and \
                    (p["data_read"] is not None or (status == "aborted" and p["reason"] == "interrupted"))
            if not valid:
                audit.v("invalid_terminal_metadata", "store", seq)
                continue
            terminal[aid] = (status, p["reason"])
            if status == "completed":
                writer = {"run_id": r["provenance"]["run_id"], "run_attempt": r["provenance"]["run_attempt"]}
                _check_links(p, aid, sseq, sp, seq, writer, by_key, linked, audit)
            if audit.scoped(sp["identity"]):
                audit.ended(status, p["data_read"])
    # results: unregistered protected evaluations and evidential weight (canonical function)
    for r in records:
        kind, p, seq = r["type"], r["payload"], r["seq"]
        if kind == "observation":
            k = tuple(r["key"])
            if epoch_seq is None or seq < epoch_seq:
                audit.legacy["protected_records"] += 1
            elif k not in linked:
                audit.v("unregistered_protected_evaluation", "store", seq)
            elif audit.scoped(starts[linked[k]][1]["identity"]):
                audit.observations += 1
            reg = by_key.get(("registration", p.get("prediction"), p.get("registration_status")))
            if reg is None:
                audit.v("registration_missing", "store", seq)
                continue
            rp = reg["payload"]
            try:
                expected = L.forward_observation_weight(eligible=bool(rp["eligible"]),
                                                        registration_weight=rp["evidential_weight"],
                                                        reconstructed=bool(p["reconstructed"]),
                                                        channel=rp.get("channel", "blind"))
                if p["evidential_weight"] != expected or p["eligible"] != rp["eligible"] or p.get("role") != "forward":
                    audit.v("evidential_weight_mismatch", "store", seq)
            except (KeyError, L.LedgerError):
                audit.v("evidential_weight_mismatch", "store", seq)
        elif kind == "screening":
            if p.get("evidential_weight") != L.evidential_weight("blind", "exploration") or \
                    p.get("role") != "exploration":
                audit.v("evidential_weight_mismatch", "store", seq)
            if tuple(r["key"]) not in linked:
                audit.legacy["unlinked_exploration"] += 1          # exploration is open; counted, not a violation
    for aid, (seq, p) in starts.items():
        if aid not in terminal and audit.scoped(p["identity"]):
            audit.counts["unfinished"] += 1
            audit.v("missing_terminal", "store", seq)
    return set(starts)


def _check_links(p, aid, sseq, sp, tseq, writer, by_key, linked, audit) -> None:
    """A ``new`` result was written by the same writer as its terminal (one journal entry: the attempt's own run,
    or the later run whose journal recovery finished that entry), after the start and before the terminal."""
    from .ops import store as ST
    allowed = {"forward_observation": ("observation", "missed_observation"), "screening": ("screening",)}[sp["kind"]]
    for link in p["results"]:
        try:
            key = tuple(link["key"])
            have = by_key.get(key)
            ok = link["type"] in allowed and link["disposition"] in ("new", "duplicate", "conflict")
            if ok and sp["kind"] == "forward_observation":
                ok = len(key) == 3 and key[1] == sp["subject"]["prediction"] and key[0] == link["type"]
            if ok and sp["kind"] == "screening":
                ok = key == ("screening", sp["identity"]["spec_hash"], sp["subject"]["window"])
            if ok and (have is None or have["seq"] > tseq):
                ok = False
            elif ok and link["disposition"] in ("new", "duplicate"):
                ok = (ST.content_hash(have["type"], have["key"], have["payload"]) == link["content_hash"]
                      and have["type"] == link["type"])
                if ok and link["disposition"] == "new":
                    ok = (sseq < have["seq"] < tseq and key not in linked and
                          {"run_id": have["provenance"]["run_id"], "run_attempt": have["provenance"]["run_attempt"]}
                          == writer)
                    if ok:
                        linked[key] = aid
            elif ok:
                conflict = by_key.get(("conflict", *key, link["content_hash"][:16]))
                ok = (conflict is not None and conflict["payload"].get("rejected_content_hash") == link["content_hash"]
                      and sseq < conflict["seq"] < tseq)
        except (KeyError, TypeError):
            ok = False
        if not ok:
            audit.v("result_linkage_mismatch", "store", tseq)


def reconcile(*, ledger_path=None, ledger_anchor=None, store_chain=None, store_anchor=None,
              batch: str | None = None) -> dict:
    """Audit either or both authoritative stores up to their anchors (BINDING_ACCOUNTING.md section 9).

    ``ledger_path``: the Manhattan ledger file. ``store_chain``: the operational Store's ``chain.jsonl`` (a clone's
    file; never the cached ``Store`` object). Each needs its anchor ``{"records": n, "head": hash}``, retained
    outside the store (the caller's responsibility; D-7). ``batch`` restricts attempt counts and attempt-level
    violations to one batch; unattributable records are always reported."""
    from .ops import store as ST
    if ledger_path is None and store_chain is None:
        raise ReconciliationError("reconciliation needs at least one authoritative store")
    if batch is not None and (not isinstance(batch, str) or not batch):
        raise ReconciliationError("batch is a batch ID")
    audit = _Audit(batch)
    covered, boundary, ids = [], {}, {}
    if ledger_path is not None:
        anchor = _anchor(ledger_anchor, "ledger")
        records, errors = L.verify_snapshot(_read(ledger_path, "ledger"))
        if errors:
            raise ReconciliationError("the ledger does not verify: " + "; ".join(errors))
        scope = _prefix(records, anchor, "ledger")
        boundary["ledger"] = {"records": anchor[0], "head": anchor[1], "beyond": len(records) - anchor[0]}
        ids["ledger"] = _ledger_pass(scope, audit)
        covered.append("ledger")
    if store_chain is not None:
        anchor = _anchor(store_anchor, "store")
        raw = _read(store_chain, "store")
        try:
            records = [json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReconciliationError("the store chain is not JSON lines") from exc
        if not all(isinstance(r, dict) for r in records) or ST.verify_chain(records):
            raise ReconciliationError("the store chain does not verify")
        scope = _prefix(records, anchor, "store")
        boundary["store"] = {"records": anchor[0], "head": anchor[1], "beyond": len(records) - anchor[0]}
        ids["store"] = _store_pass(scope, audit)
        covered.append("store")
    for aid in ids.get("ledger", set()) & ids.get("store", set()):
        audit.v("cross_store_attempt_collision", "both", None)
    legacy_blocks = audit.legacy["starts"] + audit.legacy["protected_records"]
    return {"stores_covered": covered, "boundary": boundary, "batch": batch, **audit.counts,
            "terminals_by_data_read": audit.read,
            "distinct_specifications": len(audit.specs), "completed_evaluation_keys": len(audit.keys),
            "repeated_observations": audit.observations, "independent_statistical_tests": None,
            "legacy": audit.legacy, "designated_reserve_completions": audit.designated,
            "violations": audit.violations,
            "access_reconciled": not audit.violations and not legacy_blocks and audit.counts["unfinished"] == 0,
            "limitations": list(LIMITATIONS)}
