"""Strict lifecycle-only accounting. Does NOT reconcile or authorize data access.

An independently retained head anchor is required to detect suffix deletion.
Legacy unlinked evaluations fail this audit; they are never silently registered.
"""
from pathlib import Path

from . import ledger as L


def reconcile_lifecycle(path: Path, *, anchor: str) -> dict:
    errors = L.verify(path, anchor=anchor)
    if errors:
        raise L.LedgerError('; '.join(errors))
    starts, terminal, superseded = {}, {}, set()
    retries = 0
    for r in L.read(path):
        p, kind = r['payload'], r['type']
        if kind == 'evaluation_started':
            prior = p.get('supersedes')
            if prior is not None:
                if prior not in starts or prior in terminal or prior in superseded:
                    raise L.LedgerError('invalid retry relationship')
                identity = lambda x: {k: v for k, v in x.items() if k != 'supersedes'}
                if "code_version" not in p or identity(p) != identity(starts[prior]):
                    raise L.LedgerError('contradictory retry identity')
                superseded.add(prior)
                retries += 1
            starts[r['hash']] = p
        elif kind in ('evaluation', 'rerun', 'nondeterminism', 'attempt_failed', 'attempt_aborted'):
            aid = p.get('attempt_id')
            if aid not in starts or aid in superseded:
                raise L.LedgerError('terminal record without an active registered attempt')
            if aid in terminal:
                raise L.LedgerError('duplicate or contradictory terminal status')
            if kind.startswith('attempt_'):
                if set(p) != {'attempt_id', 'reason'} or p['reason'] not in (
                        'execution_error', 'data_unavailable', 'interrupted', 'cancelled', 'validation_error'):
                    raise L.LedgerError('invalid terminal metadata')
                terminal[aid] = kind.removeprefix('attempt_')
            else:
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
