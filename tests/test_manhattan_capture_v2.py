"""Synthetic capture definitions; no legacy authentication or migration."""
import copy
import pytest
from manhattan.ops import data as D, store as ST
from test_manhattan_pit_integrity import Archive


@pytest.fixture
def archive(tmp_path):
    a = Archive(tmp_path)
    a.capture(b'series,period,value\nx,2010-01-04,1\n', '2010-01-05T12:00:00Z')
    return a


def test_valid_v2_and_missing_definition(archive):
    payload = archive.records[0]['payload']
    assert payload['source_definition']['schema_version'] == 2
    expected = D.first_seen(archive, ['synthetic'])
    del payload['source_definition']
    before = copy.deepcopy(archive.records)
    assert D.first_seen(archive, ['synthetic']) == expected
    assert archive.records == before  # no authentication, promotion or migration


@pytest.mark.parametrize('version', [1, None, '2', True, 2.0, {}, [], 3])
def test_bad_versions(archive, version):
    archive.records[0]['payload']['source_definition']['schema_version'] = version
    with pytest.raises(ST.StoreError, match='capture schema version .*expected schema version 2'):
        D.first_seen(archive, ['synthetic'])


@pytest.mark.parametrize('definition', [{}, None, [], 'v2'])
def test_malformed_definition(archive, definition):
    archive.records[0]['payload']['source_definition'] = definition
    with pytest.raises(ST.StoreError, match='expected schema version 2'):
        D.first_seen(archive, ['synthetic'])


def test_same_version_configuration_mismatch(archive):
    archive.records[0]['payload']['source_definition']['source']['lag_days'] = 200
    with pytest.raises(ST.StoreError, match='definition differs from replay configuration'):
        D.first_seen(archive, ['synthetic'])
