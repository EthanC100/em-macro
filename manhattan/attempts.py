"""Strict lifecycle-only accounting. Does NOT reconcile or authorize data access.

An independently retained head anchor is required to detect suffix deletion.
Legacy unlinked evaluations fail this audit; they are never silently registered.
"""
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
                L.require_retry_code_identity(p.get("code_version"))
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
                if set(p) != {'attempt_id', 'reason'} or p['reason'] not in (
                        'execution_error', 'data_unavailable', 'interrupted', 'cancelled', 'validation_error'):
                    raise L.LedgerError('invalid terminal metadata')
                terminal[aid] = kind.removeprefix('attempt_')
            else:
                _validate_completion(p)
                if any(p.get(k) != v for k, v in starts[aid].items() if k != 'supersedes'):
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
