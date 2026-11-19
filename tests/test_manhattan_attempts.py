"""Synthetic lifecycle accounting, not end-to-end access authorization.

Phase 4B correction: these 4A lifecycle mechanics are role-independent, so they run on the exploration role. A
reserve or forward completion can no longer be written through the storage API without a completion proof
(owner decision D-5; tests in test_manhattan_binding_access.py). Hash-valid forgeries use ``forge`` (a writer with
file access), because ``Ledger.append`` refuses lifecycle record types."""
import json
import pytest
from manhattan import ledger as L
from manhattan.attempts import reconcile_lifecycle
from manhattan_attempt_fixtures import forge
from test_manhattan_registry import ev as legacy_ev


def ev(**over):
    return legacy_ev(**{"code_version": {"commit": "a" * 40, "tree": "b" * 40},
                        "result_hash": "c" * 64, **over})


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
    forge(b, end['type'], end['payload'])
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
    for result in ('c' * 64, 'c' * 64, 'd' * 64):
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
        forge(b, 'evaluation_started', {**a['payload'], 'supersedes': a['hash']})
    else:
        x = b.start_evaluation(ev())
        forge(b, 'evaluation', {**rec['payload'], 'attempt_id': x['hash'], 'family': 'wrong'})
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


@pytest.mark.parametrize('damage', ['unlink', 'empty', 'replace'])
def test_external_anchor_detects_deleted_or_replaced_ledger(tmp_path, damage):
    b = book(tmp_path)
    b.start_evaluation(ev())
    anchor = b.head
    if damage == 'unlink':
        b.path.unlink()
    elif damage == 'empty':
        b.path.write_bytes(b'')
    else:
        replacement = L.Ledger(tmp_path / 'replacement', 'other', 'test')
        replacement.start_evaluation(ev(spec_hash='different'))
        replacement.path.replace(b.path)
    with pytest.raises(L.LedgerError):
        reconcile_lifecycle(b.path, anchor=anchor)


@pytest.mark.parametrize('anchor', [None, '', 'a' * 63, 'a' * 65, 'z' * 64, 'A' * 64,
                                   0, False, [], {}, b'a' * 64])
def test_invalid_anchor_fails_closed_even_after_deletion(tmp_path, anchor):
    b = book(tmp_path)
    b.start_evaluation(ev())
    b.path.write_bytes(b'')
    with pytest.raises(L.LedgerError, match='external.*anchor'):
        reconcile_lifecycle(b.path, anchor=anchor)


def test_anchor_is_required_and_empty_ledger_can_verify(tmp_path):
    b = book(tmp_path)
    b.path.write_bytes(b'')
    with pytest.raises(TypeError):
        reconcile_lifecycle(b.path)
    assert reconcile_lifecycle(b.path, anchor=L.GENESIS)['registered'] == 0


@pytest.mark.parametrize('damage', ['unlink', 'empty', 'replace'])
def test_reconciliation_processes_verified_snapshot_only(tmp_path, monkeypatch, damage):
    b = book(tmp_path)
    original = b.start_evaluation(ev())
    verify_snapshot = L.verify_snapshot
    captured = []

    def verify_then_change(snapshot, anchor=None):
        assert isinstance(snapshot, bytes)
        records, errors = verify_snapshot(snapshot, anchor)
        captured.append(snapshot)
        if damage == 'unlink':
            b.path.unlink()
        elif damage == 'empty':
            b.path.write_bytes(b'')
        else:
            b.path.write_text('not the verified ledger')
        return records, errors

    monkeypatch.setattr(L, 'verify_snapshot', verify_then_change)
    result = reconcile_lifecycle(b.path, anchor=b.head)
    assert len(captured) == 1
    assert result['registered'] == result['unfinished'] == 1
    assert result['unfinished_attempts'] == [original['hash']]


COMPLETION_FIELDS = ('executable', 'variant', 'hypothesis', 'family', 'batch', 'channel', 'role', 'window',
                     'designated', 'spec_hash', 'data_hash', 'code_version', 'result_hash', 'n_obs', 'summary',
                     'seed', 'reconstructed', 'evidential_weight')


@pytest.mark.parametrize('kind', ['evaluation', 'rerun', 'nondeterminism'])
@pytest.mark.parametrize('field', COMPLETION_FIELDS)
def test_incomplete_completion_is_not_counted(tmp_path, field, kind):
    b = book(tmp_path)
    a = b.start_evaluation(ev())
    payload = {**ev(), 'attempt_id': a['hash'], 'reconstructed': False, 'evidential_weight': 1}
    del payload[field]
    forge(b, kind, payload)  # hash-valid semantic corruption, not a broken chain
    with pytest.raises(L.LedgerError, match='completion schema'):
        audit(b)


def test_start_payload_alone_is_not_a_completion(tmp_path):
    b = book(tmp_path)
    a = b.start_evaluation(ev())
    forge(b, 'evaluation', {**a['payload'], 'attempt_id': a['hash']})
    with pytest.raises(L.LedgerError, match='completion schema'):
        audit(b)


@pytest.mark.parametrize('field,value', [
    ('result_hash', None), ('result_hash', ''), ('result_hash', 'unknown'),
    ('spec_hash', 'invalid'), ('data_hash', 'invalid'), ('summary', []), ('n_obs', True), ('n_obs', -1),
    ('seed', '7'), ('code_version', None), ('window', None), ('role', 'unknown'),
    ('channel', None), ('designated', 1), ('reconstructed', None), ('evidential_weight', True),
])
def test_malformed_completion_is_not_counted(tmp_path, field, value):
    b = book(tmp_path)
    a = b.start_evaluation(ev())
    payload = {**ev(), 'attempt_id': a['hash'], 'reconstructed': False, 'evidential_weight': 1,
               field: value}
    forge(b, 'evaluation', payload)
    with pytest.raises(L.LedgerError, match='completion schema'):
        audit(b)


BAD_CODE = [None, {}, 'unknown',
            {'commit': '0' * 40, 'tree': 'b' * 40},
            {'commit': 'a' * 40, 'tree': '0' * 40},
            {'commit': 'a' * 40, 'engine_sha256': '0' * 64}, {'commit': None}, {'commit': 'unknown', 'tree': 'b' * 40},
            {'commit': 'a' * 40}, {'commit': 'a' * 40, 'tree': None},
            {'commit': 'a' * 40, 'tree': 'unknown'}, {'commit': True, 'tree': 'b' * 40},
            {'commit': 'a' * 40, 'engine_sha256': 'z' * 64},
            {'commit': 'a' * 40, 'engine_sha256': 'b' * 63},
            {'commit': 'a' * 40, 'tree': 'b' * 40, 'engine_sha256': None}]


@pytest.mark.parametrize('version', BAD_CODE)
def test_unknown_code_cannot_create_or_certify_retry(tmp_path, version):
    b = book(tmp_path)
    a = b.start_evaluation(ev(code_version=version))  # non-retry legacy API stays compatible
    before = b.head
    with pytest.raises(L.LedgerError, match='code identity'):
        b.start_evaluation(ev(code_version=version), supersedes=a['hash'])
    assert b.head == before
    forge(b, 'evaluation_started', {**a['payload'], 'supersedes': a['hash']})
    with pytest.raises(L.LedgerError, match='code identity'):
        audit(b)


def test_missing_retry_code_is_rejected_in_writer_and_reconciliation(tmp_path):
    b = book(tmp_path)
    payload = ev()
    del payload['code_version']
    a = b.start_evaluation(payload)
    with pytest.raises(L.LedgerError, match='code identity'):
        b.start_evaluation(payload, supersedes=a['hash'])
    forge(b, 'evaluation_started', {**a['payload'], 'supersedes': a['hash']})
    with pytest.raises(L.LedgerError, match='code identity'):
        audit(b)


@pytest.mark.parametrize('version', [
    {'commit': 'a' * 40, 'tree': 'b' * 40},
    {'commit': 'a' * 40, 'engine_sha256': 'b' * 64},
    {'commit': 'a' * 64, 'tree': 'b' * 64},
])
def test_known_retry_code_is_supported(tmp_path, version):
    b = book(tmp_path)
    a = b.start_evaluation(ev(code_version=version))
    b.start_evaluation(ev(code_version=version), supersedes=a['hash'])
    assert audit(b)['retries'] == 1
