"""Synthetic lifecycle accounting, not end-to-end access authorization."""
import json
import pytest
from manhattan import ledger as L
from manhattan.attempts import reconcile_lifecycle
from test_manhattan_registry import ev


def book(tmp_path):
    return L.Ledger(tmp_path / 'ledger.jsonl', 'synthetic', 'test')


def audit(b):
    return reconcile_lifecycle(b.path, anchor=b.head)


def test_denominator_retry_and_variants(tmp_path):
    b = book(tmp_path)
    a = b.start_evaluation(ev())
    retry = b.start_evaluation(ev(), supersedes=a['hash'])
    b.record_evaluation(**ev(), attempt_id=retry['hash'])
    for status in ('failed', 'aborted'):
        x = b.start_evaluation(ev(spec_hash=status, variant=status))
        b.end_attempt(x['hash'], status=status, reason='interrupted')
    result = audit(b)
    assert (result['registered'], result['completed'], result['failed'], result['aborted'],
            result['unfinished'], result['retries'], result['distinct_specifications']) == (4, 1, 1, 1, 1, 1, 3)
    assert result['unfinished_attempts'] == [a['hash']]
    assert not result['access_reconciled']
    with pytest.raises(L.LedgerError):
        b.start_evaluation(ev(), supersedes=retry['hash'])
    with pytest.raises(L.LedgerError):
        b.record_evaluation(**ev(), attempt_id=retry['hash'])
    with pytest.raises(L.LedgerError):
        b.record_evaluation(**ev(), attempt_id=a['hash'])


@pytest.mark.parametrize('damage', ['delete', 'alter', 'truncate'])
def test_chain_damage(tmp_path, damage):
    b = book(tmp_path)
    a = b.start_evaluation(ev())
    b.record_evaluation(**ev(), attempt_id=a['hash'])
    b.start_evaluation(ev(spec_hash='other'))
    rows = b.path.read_text().splitlines()
    if damage == 'delete':
        del rows[1]
    elif damage == 'truncate':
        rows.pop()
    else:
        r = json.loads(rows[1]); r['payload']['summary'] = {}; rows[1] = json.dumps(r)
    b.path.write_text('\n'.join(rows) + '\n')
    with pytest.raises(L.LedgerError):
        audit(b)


def test_unregistered_and_duplicate_terminal(tmp_path):
    b = book(tmp_path)
    b.record_evaluation(**ev())
    with pytest.raises(L.LedgerError, match='registered'):
        audit(b)
    b = L.Ledger(tmp_path / 'other', 'test', 'test')
    a = b.start_evaluation(ev())
    end = b.end_attempt(a['hash'], status='failed', reason='execution_error')
    b.append(end['type'], end['payload'])
    with pytest.raises(L.LedgerError, match='duplicate'):
        audit(b)


def test_identity_and_safe_reasons(tmp_path):
    b = book(tmp_path)
    a = b.start_evaluation(ev())
    with pytest.raises(L.LedgerError, match='identity'):
        b.start_evaluation(ev(variant='different'), supersedes=a['hash'])
    with pytest.raises(L.LedgerError, match='identity'):
        b.record_evaluation(**ev(family='other'), attempt_id=a['hash'])
    with pytest.raises(L.LedgerError, match='classification'):
        b.end_attempt(a['hash'], status='failed', reason='private performance text')
    assert audit(b)['unfinished'] == 1


def test_reruns_keep_results_and_attempts(tmp_path):
    b = book(tmp_path)
    first = None
    for result in ('unfavorable', 'unfavorable', 'different'):
        a = b.start_evaluation(ev())
        rec = b.record_evaluation(**ev(result_hash=result), attempt_id=a['hash'])
        first = first or rec
    assert [r['type'] for r in b._evaluations()] == ['evaluation', 'rerun', 'nondeterminism']
    assert b.looks() == 1 and audit(b)['completed'] == 3
    assert b.result_of_record(ev()['spec_hash'], ev()['window']['id']) == first
    assert b.suspended_families() == {'AF-1'}


@pytest.mark.parametrize('forgery', ['retry', 'identity'])
def test_semantic_forgery_with_valid_chain(tmp_path, forgery):
    b = book(tmp_path)
    a = b.start_evaluation(ev())
    rec = b.record_evaluation(**ev(), attempt_id=a['hash'])
    if forgery == 'retry':
        b.append('evaluation_started', {**a['payload'], 'supersedes': a['hash']})
    else:
        x = b.start_evaluation(ev())
        b.append('evaluation', {**rec['payload'], 'attempt_id': x['hash'], 'family': 'wrong'})
    with pytest.raises(L.LedgerError):
        audit(b)


def test_legacy_rerun_cannot_hide_superseded_attempt(tmp_path):
    b = book(tmp_path)
    original = b.start_evaluation(ev())
    retry = b.start_evaluation(ev(), supersedes=original['hash'])
    b.record_evaluation(**ev(), attempt_id=retry['hash'])
    b.record_evaluation(**ev())  # supported legacy rerun, no active start
    assert b.unfinished() == [original]
    with pytest.raises(L.LedgerError, match='registered'):
        audit(b)  # legacy execution cannot be certified as attempt-accounted
