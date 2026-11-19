"""Capture contracts and forward attribution; synthetic fixtures only."""
from dataclasses import replace
from datetime import date

import pytest

from manhattan.availability import AvailabilityError
from manhattan.engine import evaluate, pit
from manhattan.ops import data as D, timing as TM
from test_manhattan_ops_runner import setup
import manhattan_attempt_fixtures as F
from manhattan import ledger as L, roles


@pytest.mark.parametrize('source', D.SOURCES.values())
def test_existing_daily_contracts(source):
    assert D.capture_registry([source])[source.id] == source


@pytest.mark.parametrize('changes', [
    {'frequency': 'monthly', 'period_label': 'period_start'},
    {'frequency': 'quarterly', 'period_label': 'period_end'},
    {'frequency': 'weekly'}, {'frequency': 'irregular'},
    {'availability_kind': 'release_dates'},
    {'frequency': None}, {'period_label': ''},
    {'source_reference': ''}, {'day_mapping': None}, {'lag_days': True},
])
def test_invalid_contract_rejected_before_capture(changes):
    source = replace(D.SOURCES['synthetic'], **changes)
    with pytest.raises(AvailabilityError):
        D.capture_registry([source])
    with pytest.raises(AvailabilityError):
        D.capture_intent(source, b'series,period,value\nx,2010-01-01,1\n',
                         TM.parse_time('2010-01-02T12:00:00Z'))


def test_conflicting_declarations():
    source = D.SOURCES['synthetic']
    with pytest.raises(AvailabilityError, match='conflicting'):
        D.capture_registry([source, replace(source, source_reference='different')])


def test_forward_evaluator_refuses_unattributable_reconstruction(monkeypatch, tmp_path):
    store = pit.PitStore()
    store.add('x', ['2010-01-01'], [1], lag_days=0, reconstructed=True)
    store.add('x', ['2010-01-04'], [2], lag_days=0)
    # Phase 4B: a forward window exists only for a registered attempt (synthetic fence, freeze before the window)
    book = L.Ledger(tmp_path / 'ledger.jsonl', writer='fixture', protocol='0' * 64)
    fence = roles.Fence(exploration_end=date(2009, 12, 31), reserve={}, enabled=False)
    ctx = F.register(book, store, domain='test', start=date(2010, 1, 4), end=date(2010, 1, 5), role='forward',
                     fence=fence, freeze=date(2010, 1, 3))
    window = ctx.window(store)
    monkeypatch.setattr(evaluate.backtest, 'run', lambda *a: pytest.fail('must reject before evaluation'))
    with pytest.raises(pit.PitError, match='per-observation provenance'):
        evaluate.evaluate(window, None, ledger=book, **F.spec_kwargs(), attempt=ctx)
    assert book.records()[-1]['type'] == 'attempt_failed' and not ctx.data_read


def test_nightly_forward_survives_reconstructed_warmup(setup):
    s = setup
    s['night'](date(2026, 11, 12), '2026-11-12T23:30:00Z')
    s['register']()
    s['night'](date(2026, 11, 13), '2026-11-13T23:30:00Z')
    s['night'](date(2026, 11, 16), '2026-11-16T23:30:00Z')
    ledger = s['ledger']()
    fs = D.first_seen(ledger, ('synthetic',))
    assert fs.backfill
    with pytest.raises(pit.PitError):
        fs.pit_store().require_historical_evidence()
    observations = [r['payload'] for r in ledger.of_type('observation') if r['payload']['date'] == '2026-11-16']
    assert observations
    assert all(not r['reconstructed'] and r['evidential_weight'] == 1 for r in observations)
