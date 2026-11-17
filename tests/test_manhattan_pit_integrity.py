"""Bounded data-only fixtures: no hypotheses, strategies or real datasets."""
import copy
from dataclasses import replace
from datetime import date, datetime
import itertools
import subprocess

import numpy as np
import pytest

from manhattan import roles
from manhattan.engine import pit
from manhattan.ops import data as D, store as ST, timing as TM

START, END = date(2010, 1, 4), date(2010, 1, 15)
FENCE = roles.Fence(date(2019, 12, 31), {}, False)


def window(store):
    return pit.Reader(store, caller="session", domain="synthetic_data_only", fence=FENCE).window(START, END)


def csv(*rows):
    return ("series,period,value\n" + "".join(f"x,{p},{v}\n" for p, v in rows)).encode()


class Archive:
    """Tiny captured-byte fixture; production Store verifies the chain before replay."""
    def __init__(self, path):
        self.path, self.records = path, []

    def raw_path(self, digest):
        return self.path / digest

    def of_type(self, kind):
        return [r for r in self.records if r["type"] == kind]

    def capture(self, raw, at):
        intent, _ = D.capture_intent(D.SOURCES["synthetic"], raw, TM.parse_time(at))
        self.raw_path(intent.payload["sha256"]).write_bytes(raw)
        self.records.append({"type": "capture", "key": list(intent.key), "payload": copy.deepcopy(intent.payload),
                             "provenance": {"source": intent.source, "retrieved_utc": intent.retrieved_utc}})


def test_conflicting_same_vintage_is_rejected_atomically():
    store = pit.PitStore()
    store.add("x", [START], [10.0], lag_days=0)
    before = store.data_hash()
    with pytest.raises(pit.PitError):
        store.add("x", [START], [20.0], available=[START])
    assert store.data_hash() == before and window(store).as_of("x", START)[1].tolist() == [10.0]
    fresh = pit.PitStore()
    with pytest.raises(pit.PitError):
        fresh.add("x", [START, START], [10.0, 20.0], lag_days=0)
    assert fresh.names() == []


def test_exact_vintage_duplicates_are_idempotent():
    store = pit.PitStore()
    store.add("x", [START], [10.0], lag_days=0)
    before = store.data_hash()
    store.add("x", [START, START], [10.0, 10.0], lag_days=0)
    assert store.data_hash() == before


def test_signed_zero_vintage_conflict_does_not_make_hash_arrival_dependent():
    store = pit.PitStore()
    store.add("x", [START], [0.0], lag_days=0)
    with pytest.raises(pit.PitError):
        store.add("x", [START], [-0.0], lag_days=0)


@pytest.mark.parametrize("cutoff", [None, "NaT", np.datetime64("NaT"), "2010-01-05T12:00:00"])
def test_missing_or_intraday_query_cannot_expose_data(cutoff):
    store = pit.PitStore()
    store.add("x", [START, END], [10.0, 20.0], lag_days=0)
    with pytest.raises(pit.PitError):
        window(store).as_of("x", cutoff)


@pytest.mark.parametrize("available", [["2010-01-04T18:00:00"],
                                      [datetime(2010, 1, 4, 18)], [np.datetime64("2010-01-04T18:00")]])
def test_daily_store_refuses_silent_loss_of_release_time(available):
    with pytest.raises(pit.PitError):
        pit.PitStore().add("x", [START], [10.0], available=available)


def test_midnight_numpy_daily_arrays_remain_compatible():
    store = pit.PitStore()
    store.add("x", np.array([START], dtype="datetime64[ns]"), [10.0], lag_days=0)
    assert window(store).as_of("x", START)[1].tolist() == [10.0]


def test_window_arrays_cannot_mutate_stored_history():
    store = pit.PitStore()
    store.add("x", [START, END], [10.0, 20.0], lag_days=0)
    before = store.data_hash()
    periods, values, available = window(store).as_of_with_availability("x", END)
    periods[0], values[0], available[0] = np.datetime64("2011-01-01"), 999, np.datetime64("2011-01-01")
    assert store.data_hash() == before
    assert window(store).as_of("x", START)[1].tolist() == [10.0]


@pytest.mark.parametrize("lag", [True, -1, 0.5, "1", float("nan"), float("inf")])
def test_spec_lag_is_not_silently_shortened(lag):
    with pytest.raises(pit.PitError):
        pit.lags_from_spec({"data_sources": [{"name": "x", "publication_lag_days": lag}]})


def test_conflicting_lag_definitions_are_rejected():
    with pytest.raises(pit.PitError):
        pit.lags_from_spec({"data_sources": [{"name": "x", "publication_lag_days": 1},
                                             {"name": "x", "publication_lag_days": 2}]})


def test_vintages_delays_and_replay_match_a_data_only_oracle():
    rows = [("2010-01-04", "2010-01-05", 10.0), ("2010-01-05", "2010-01-11", 20.0),
            ("2010-01-04", "2010-01-12", 11.0), ("2010-01-06", "2010-01-06", 30.0)]
    hashes, replays = set(), []
    for order in itertools.islice(itertools.permutations(rows), 8):
        store = pit.PitStore()
        for period, available, value in order:
            store.add("x", [period], [value], available=[available])
        hashes.add(store.data_hash())
        replay = []
        for t in np.arange(np.datetime64(START), np.datetime64(END) + np.timedelta64(1, "D")):
            expected = {}
            for p, a, v in sorted(rows, key=lambda r: (r[0], r[1])):
                if np.datetime64(a) <= t:
                    expected[p] = v
            p, v, a = window(store).as_of_with_availability("x", t)
            assert list(zip(p.astype(str), v)) == sorted(expected.items())
            assert (a <= t).all() and (p <= t).all()
            replay.append(v.tolist())
        replays.append(replay)
    assert len(hashes) == 1 and all(r == replays[0] for r in replays)


def test_future_releases_change_dataset_version_but_not_past_answers():
    store = pit.PitStore()
    store.add("x", [START], [10.0], available=["2010-01-05"])
    before, version = window(store).as_of("x", "2010-01-06"), store.data_hash()
    store.add("x", [START], [999.0], available=[END])
    assert store.data_hash() != version
    for left, right in zip(before, window(store).as_of("x", "2010-01-06")):
        np.testing.assert_array_equal(left, right)
    assert window(store).as_of("x", END)[1].tolist() == [999.0]


@pytest.mark.parametrize("stamp", [None, "NaT"])
def test_missing_publication_or_observation_date_is_refused(stamp):
    with pytest.raises(pit.PitError):
        pit.PitStore().add("x", [stamp], [10.0], lag_days=0)
    with pytest.raises(pit.PitError):
        pit.PitStore().add("x", [START], [10.0], available=[stamp])


@pytest.mark.parametrize("retrieved", [datetime(2010, 1, 4), None])
def test_capture_requires_an_observed_time_with_zone(retrieved):
    with pytest.raises((ValueError, TypeError)):
        D.capture_intent(D.SOURCES["synthetic"], csv(("2010-01-04", 10)), retrieved)


def test_same_release_conflict_is_not_misclassified_as_a_later_revision():
    raw = csv(("2010-01-04", 10), ("2010-01-04", 20))
    with pytest.raises(ValueError):
        D.capture_intent(D.SOURCES["synthetic"], raw, TM.parse_time("2010-01-04T21:00:00Z"))


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_nonfinite_synthetic_capture_is_not_complete_data(value):
    with pytest.raises(ValueError):
        D.capture_intent(D.SOURCES["synthetic"], csv(("2010-01-04", value)),
                         TM.parse_time("2010-01-04T21:00:00Z"))


def test_fabricated_fred_format_rejects_conflicts_and_nonfinite_quotes():
    source = D.SOURCES["fred_DEXBZUS"]
    header = "observation_date,DEXBZUS\n"
    for token in ("nan", "inf", "-inf"):
        with pytest.raises(ValueError):
            D.parse(source, (header + f"2010-01-04,{token}\n").encode())
    with pytest.raises(ValueError):
        D.parse(source, (header + "2010-01-04,2\n2010-01-04,3\n").encode())


def test_fabricated_fred_missing_markers_remain_gaps():
    raw = b"observation_date,DEXBZUS\n2010-01-04,.\n2010-01-05,\n2010-01-06,2\n"
    assert D.parse(D.SOURCES["fred_DEXBZUS"], raw) == [("fx_BRL", "2010-01-06", 0.5)]


def test_archive_first_seen_revision_delay_and_backfill_are_distinct(tmp_path):
    archive = Archive(tmp_path)
    archive.capture(csv(("2010-01-01", 9), ("2010-01-04", 10)), "2010-01-04T21:59:59Z")
    archive.capture(csv(("2010-01-04", 99), ("2010-01-05", 20)), "2010-01-11T21:00:00Z")
    first, again = D.first_seen(archive, ("synthetic",)), D.first_seen(archive, ("synthetic",))
    assert first.values[("x", "2010-01-04")] == 10 and first.revisions == 1
    assert first.available[("x", "2010-01-04")] == START
    assert first.available[("x", "2010-01-05")] == date(2010, 1, 11)
    assert ("x", "2010-01-05") in first.late
    assert first.reconstructed(["x"], "2010-01-01")  # backfill is not a verified first release
    assert first.pit_store().data_hash() == again.pit_store().data_hash()
    assert window(first.pit_store()).as_of("x", "2010-01-08")[1].tolist() == [10.0]


@pytest.mark.parametrize("at,expected", [("2010-01-04T21:59:59Z", START),
                                        ("2010-01-04T22:00:00Z", date(2010, 1, 5)),
                                        ("2010-07-07T21:00:00Z", date(2010, 7, 8))])
def test_observation_time_close_and_dst_are_explicit(at, expected):
    assert D._seen_day(TM.calendar("synthetic"), TM.parse_time(at)) == expected


@pytest.mark.parametrize("at", ["2010-01-04T22:00:00Z", "2010-01-04T23:00:00Z"])
def test_first_capture_after_close_cannot_backdate_current_day(tmp_path, at):
    archive = Archive(tmp_path)
    archive.capture(csv(("2010-01-01", 9), ("2010-01-04", 10)), at)
    fs = D.first_seen(archive, ("synthetic",))
    assert fs.available[("x", "2010-01-04")] == date(2010, 1, 5)
    assert window(fs.pit_store()).as_of("x", START)[1].size == 0
    assert fs.reconstructed(["x"], "2010-01-04")  # evidence classification stays conservative
    assert fs.available[("x", "2010-01-01")] == date(2010, 1, 1)


def test_raw_version_hash_integrity_is_already_enforced(tmp_path):
    archive = Archive(tmp_path)
    archive.capture(csv(("2010-01-04", 10)), "2010-01-04T21:00:00Z")
    archive.raw_path(archive.records[0]["payload"]["sha256"]).write_bytes(csv(("2010-01-04", 99)))
    with pytest.raises(ST.StoreError, match="hash"):
        D.first_seen(archive, ("synthetic",))


def test_new_capture_binds_source_definition(tmp_path, monkeypatch):
    archive = Archive(tmp_path)
    archive.capture(csv(("2010-01-04", 10)), "2010-01-04T21:00:00Z")
    assert "source_definition" in archive.records[0]["payload"]
    monkeypatch.setitem(D.SOURCES, "synthetic", replace(D.SOURCES["synthetic"], lag_days=2))
    with pytest.raises(ST.StoreError):
        D.first_seen(archive, ("synthetic",))


@pytest.mark.parametrize("field", ["key", "source", "bytes", "rows", "first_period", "last_period", "sha256"])
def test_capture_provenance_conflicts_fail_closed(tmp_path, field):
    archive = Archive(tmp_path)
    archive.capture(csv(("2010-01-04", 10)), "2010-01-04T21:00:00Z")
    rec = archive.records[0]
    if field == "key":
        rec["key"][1] = "other_source"
    elif field == "source":
        rec["provenance"]["source"] = "other_source"
    elif field in ("bytes", "rows"):
        rec["payload"][field] += 1
    elif field == "sha256":
        rec["payload"]["sha256"] = "not-a-version-hash"
    else:
        rec["payload"][field] = "2010-01-05"
    with pytest.raises(ST.StoreError):
        D.first_seen(archive, ("synthetic",))


def test_legacy_capture_is_not_upgraded_to_verified_source_provenance(tmp_path):
    archive = Archive(tmp_path)
    archive.capture(csv(("2010-01-04", 10)), "2010-01-04T21:00:00Z")
    archive.records[0]["payload"].pop("source_definition", None)
    assert D.first_seen(archive, ("synthetic",)).values[("x", "2010-01-04")] == 10


@pytest.mark.parametrize("n", [-1, 1.5, True])
def test_query_length_is_not_an_implicit_slice_or_boolean(n):
    store = pit.PitStore()
    store.add("x", [START], [10], lag_days=0)
    with pytest.raises(pit.PitError):
        window(store).as_of("x", START, n=n)


def test_query_zero_periods_is_empty():
    store = pit.PitStore()
    store.add("x", [START], [10], lag_days=0)
    assert window(store).as_of("x", START, n=0)[0].size == 0


def test_calendar_configuration_drift_does_not_silently_replay(tmp_path, monkeypatch):
    archive = Archive(tmp_path)
    archive.capture(csv(("2010-01-04", 10)), "2010-01-04T21:00:00Z")
    cal = TM.CALENDARS["synthetic"]
    monkeypatch.setitem(TM.CALENDARS, "synthetic", replace(cal, tz="UTC"))
    with pytest.raises(ST.StoreError):
        D.first_seen(archive, ("synthetic",))


@pytest.mark.parametrize("stamp", [None, "2010-01-04T21:00:00"])
def test_archive_requires_observation_time_to_be_present_and_zoned(tmp_path, stamp):
    archive = Archive(tmp_path)
    archive.capture(csv(("2010-01-04", 10)), "2010-01-04T21:00:00Z")
    archive.records[0]["provenance"]["retrieved_utc"] = stamp
    with pytest.raises(ValueError):
        D.first_seen(archive, ("synthetic",))


def test_unknown_source_does_not_silently_produce_an_empty_dataset(tmp_path):
    with pytest.raises(ST.StoreError):
        D.first_seen(Archive(tmp_path), ("missing_source",))


def test_recapturing_identical_legacy_bytes_does_not_rewrite_or_create_conflict(tmp_path):
    from manhattan.ops import runner as R

    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    raw = csv(("2010-01-04", 10))
    at = TM.parse_time("2010-01-04T21:00:00Z")
    it, files = D.capture_intent(D.SOURCES["synthetic"], raw, at)
    it.payload.pop("source_definition")
    old = ST.Store(workdir=tmp_path / "old", remote=str(remote), run_id="old", clock=lambda: at).open()
    old.write([it], "synthetic legacy capture", files=files)
    original = old.of_type("capture")[0]
    cfg = R.RunConfig(ledger_dir=tmp_path / "private/ledger", private_dir=tmp_path / "private",
                      remote=str(remote), batches_dir=tmp_path / "no-batches", asof=START,
                      sources=("synthetic",), run_id="current", run_calendar="synthetic")
    health = R.nightly(cfg, {"synthetic": lambda: raw}, clock=lambda: at)
    final = ST.Store(workdir=tmp_path / "check", remote=str(remote)).open()
    assert health["status"] == "ok" and health["captures_new"] == 0
    assert final.of_type("capture") == [original] and final.of_type("conflict") == []
