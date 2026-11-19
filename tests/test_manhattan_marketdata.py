"""Manhattan market-data layer (manhattan/marketdata, docs/manhattan/marketdata/DESIGN.md).

Synthetic fixtures only: fictitious roots XA/XB, deterministic values, no licensed byte and no network. Tests of
code alone: they always run (manhattan/testing.py convention). Groups: schema and provenance; deterministic
ingestion and immutable identity; validation; adapters; the fence (reserve/forward never read without
authorisation); point-in-time availability, revisions and look-ahead; missing data.
"""
from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone

import pytest

from manhattan import roles
from manhattan.availability import validate_source
from manhattan.engine.pit import PitError
from manhattan.marketdata import continuous as CT
from manhattan.marketdata.adapters import fixture as FX
from manhattan.marketdata.adapters.databento import (DatabentoStatisticsAdapter, databento_source, plan_request)
from manhattan.marketdata.adapters.norgate import NorgateExportAdapter, norgate_source
from manhattan.marketdata.errors import (FenceRefused, ImmutableError, LicenceError, MarketDataError, NotAuthorized,
                                         ProvenanceError, SchemaError, ValidationFailed)
from manhattan.marketdata.ingest import ingest
from manhattan.marketdata.provenance import SourceDescriptor
from manhattan.marketdata.schema import AdjustmentEvent, Instrument, Observation, parse_contract
from manhattan.marketdata.store import REPO_ROOT, DatasetStore
from manhattan.marketdata.timing import BACKFILL, FIRST_SEEN, LATE, VENDOR, ResearchClock, availability
from manhattan.marketdata.validate import Rules, validate
from manhattan.marketdata.vintages import VintageSet, series_name

UTC = timezone.utc
RETRIEVED = datetime(2026, 11, 19, 0, 0, tzinfo=UTC)
FENCE = roles.Fence(date(2019, 12, 31), {}, False)                      # the default: no reserve
CLOCK = ResearchClock("America/New_York", time(17, 0))
INST = FX.synthetic_instruments()
XA = FX.synthetic_contracts("XA", "SYN_XA", 2018, 2020)
NG_SRC = norgate_source(delay_minutes=600, delay_reference="synthetic test assumption",
                        owner_approval="synthetic test (not an owner decision)")
DB_SRC = databento_source()
DB_REQ = {"ts_format": "ns", "price_format": "fixed_1e9"}


@pytest.fixture
def store(tmp_path):
    return DatasetStore(tmp_path / "store", allow_licensed=True)


def norgate(files, store, *, retrieved=RETRIEVED, policy="exclude", src=NG_SRC, fence=FENCE, caller="session", **kw):
    return ingest(NorgateExportAdapter({"XA": "SYN_XA"}, INST, src), files, request={"snapshot": "synthetic"},
                  retrieved_utc=retrieved, instruments=INST, store=store, fence=fence, caller=caller,
                  policy=policy, **kw)


def fixture_csv(rows, cols=("instrument_id", "contract_id", "session_date", "field", "value", "settlement_status",
                            "observed_at_utc", "published_at_utc")) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(cols), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in cols})
    return buf.getvalue().encode()


def fx_rows(start, end, value=lambda d: 1.0 + d.toordinal() % 7 / 100):
    from manhattan.marketdata.schema import session_dates
    return [{"instrument_id": "SYN_FXAB", "session_date": d.isoformat(), "field": "mid", "value": repr(value(d))}
            for d in session_dates(start, end)]


def ingest_fixture(rows, store, *, retrieved=RETRIEVED, src=FX.SYNTHETIC_EOD, **kw):
    kw.setdefault("fence", FENCE)
    kw.setdefault("caller", "session")
    return ingest(FX.FixtureAdapter(src), {"fixture.csv": fixture_csv(rows)}, request={"fixture": "t"},
                  retrieved_utc=retrieved, instruments=INST, store=store, **kw)


def obs(**kw):
    base = dict(instrument_id="SYN_XA", contract_id="XA-2019H", session_date=date(2019, 2, 1), field="settle",
                value=50.0, source_id=FX.SYNTHETIC_EOD.source_id, first_seen_utc=RETRIEVED)
    base.update(kw)
    return Observation(**base)


def codes(rows, *, contracts=XA, retrieved=RETRIEVED, src=FX.SYNTHETIC_EOD, rules=Rules()):
    _, rep = validate(rows, INST, contracts, src, retrieved, rules)
    return rep.codes()


# ================================================================ schema and provenance

def test_schema_refuses_naive_times_nan_and_bad_ids():
    with pytest.raises(SchemaError, match="naive"):
        obs(first_seen_utc=datetime(2026, 1, 1))
    with pytest.raises(SchemaError, match="finite"):
        obs(value=float("nan"))
    with pytest.raises(SchemaError):
        obs(contract_id="XA2019H")
    with pytest.raises(SchemaError, match="field"):
        obs(field="price")
    assert parse_contract("XA-2019H") == ("XA", 2019, 3)


def test_instrument_rules_by_asset_class():
    with pytest.raises(SchemaError, match="quote currency"):
        Instrument("P", "fx_spot", "fx_daily", "America/New_York", time(17), "AAA", base="AAA", quote="BBB")
    with pytest.raises(SchemaError, match="maturity"):
        Instrument("B", "bond_cash", "bonds_daily", "Europe/London", time(16, 30), "GBP", price_basis="clean")
    with pytest.raises(SchemaError, match="multiplier"):
        Instrument("F", "future", "futures_daily", "America/Chicago", time(13, 30), "USD", root="F")
    with pytest.raises(SchemaError, match="time zone"):
        Instrument("F", "future", "futures_daily", "Mars/Olympus", time(13, 30), "USD", root="F", multiplier=1.0,
                   tick=0.1)
    # DST: the same local close is a different UTC time in winter and summer
    xa = INST["SYN_XA"]
    assert xa.close_utc(date(2019, 1, 15)).hour == 19 and xa.close_utc(date(2019, 7, 15)).hour == 18


def test_adjustment_events_need_announcement_and_reference():
    with pytest.raises(SchemaError, match="announced"):
        AdjustmentEvent("SYN_XA", "price_unit_change", date(2019, 1, 2), None, factor=0.01, reference="notice")
    with pytest.raises(SchemaError, match="reference"):
        AdjustmentEvent("SYN_XA", "multiplier_change", date(2019, 1, 2), RETRIEVED, factor=2.0)
    with pytest.raises(SchemaError, match="roll"):
        AdjustmentEvent("SYN_XA", "roll", date(2019, 1, 2), RETRIEVED)


def test_source_descriptors_never_invent_provenance():
    with pytest.raises(ProvenanceError, match="never redistributable"):
        replace(DB_SRC, redistribution=True)
    with pytest.raises(ProvenanceError, match="licence"):
        SourceDescriptor("x", "v", "d", "public", True, "declared_delay", 0)
    bare = norgate_source()                              # the shipped Norgate descriptor declares no delay
    assert not bare.availability_ready
    assert len(bare.provenance_gaps()) == 3
    with pytest.raises(ProvenanceError):
        bare.availability_contract()
    for src in (NG_SRC, DB_SRC, FX.SYNTHETIC_EOD, FX.SYNTHETIC_RECEIPT):  # interoperable with manhattan.availability
        validate_source(src.availability_contract())
    with pytest.raises(ProvenanceError, match="vendor_receipt"):
        replace(DB_SRC, declared_delay_minutes=5)


def test_adapters_refuse_to_fetch():
    for ad in (NorgateExportAdapter({"XA": "SYN_XA"}, INST), DatabentoStatisticsAdapter(INST), FX.FixtureAdapter()):
        with pytest.raises(NotAuthorized):
            ad.fetch({"symbols": ["XAH9"]})
    with pytest.raises(SchemaError, match="synthetic"):
        FX.FixtureAdapter(DB_SRC)


# ================================================================ deterministic ingestion, immutable identity

def test_ingestion_is_deterministic_and_idempotent(tmp_path):
    files = FX.synthetic_norgate_export(XA, date(2019, 12, 31))
    a = DatasetStore(tmp_path / "a", allow_licensed=True)
    b = DatasetStore(tmp_path / "b", allow_licensed=True)
    r1 = norgate(files, a)
    r2 = norgate(dict(reversed(list(files.items()))), b)          # files in another order, another machine
    assert r1.dataset_id == r2.dataset_id and r1.created and r2.created
    for name in ("manifest.json", "rows.csv", "reference.json", "validation.json"):
        assert (a.path(r1.dataset_id) / name).read_bytes() == (b.path(r2.dataset_id) / name).read_bytes()
    again = norgate(files, a)
    assert again.dataset_id == r1.dataset_id and not again.created
    assert len(a.registry()) == 1 and a.verify() == 1
    assert norgate(files, a, retrieved=RETRIEVED + timedelta(seconds=1)).dataset_id != r1.dataset_id
    ad = NorgateExportAdapter({"XA": "SYN_XA"}, INST, NG_SRC)
    ad.version = "2"
    r3 = ingest(ad, files, request={"snapshot": "synthetic"}, retrieved_utc=RETRIEVED, instruments=INST, store=a,
                fence=FENCE, caller="session", policy="exclude")
    assert r3.dataset_id != r1.dataset_id
    assert a.verify() == 3


def test_manifest_records_identity_and_provenance(store):
    files = FX.synthetic_norgate_export(XA, date(2019, 12, 31))
    r = norgate(files, store)
    m = store.load(r.dataset_id)["manifest"]
    assert r.dataset_id.startswith("MD-") and len(r.dataset_id) == 19
    assert {f["name"] for f in m["raw_files"]} == set(files)
    assert m["source"]["licence"] == "licensed" and m["source"]["redistribution"] is False
    assert m["retrieved_utc"] == "2026-11-19T00:00:00.000000Z" and m["provenance_gaps"] == []
    assert any("last_quoted_date" in n for n in m["notes"])
    gaps = norgate(files, store, src=norgate_source())          # stored, but flagged incomplete
    assert len(store.load(gaps.dataset_id)["manifest"]["provenance_gaps"]) == 3
    assert store.registry()[-1]["provenance_complete"] is False


def test_stored_datasets_are_immutable_and_tamper_evident(store):
    r = ingest_fixture(fx_rows(date(2019, 1, 1), date(2019, 3, 29)), store)
    d = store.path(r.dataset_id)
    assert not os.access(d / "rows.csv", os.W_OK) or os.geteuid() == 0     # read-only (root ignores modes)
    original = {n: (d / n).read_bytes() for n in ("rows.csv", "reference.json", "validation.json")}
    (d / "rows.csv").chmod(0o644)
    (d / "rows.csv").write_bytes(original["rows.csv"].replace(b"1.0", b"1.5", 1))
    with pytest.raises(ImmutableError, match="rows.csv"):
        store.load(r.dataset_id)
    with pytest.raises(ImmutableError, match="different contents"):    # the honest bytes cannot overwrite either
        store.put(r.manifest, original["rows.csv"], original["reference.json"], original["validation.json"])
    with pytest.raises(ProvenanceError):                                 # rows that do not match their manifest
        store.put(r.manifest, original["rows.csv"] + b"x", original["reference.json"], original["validation.json"])
    reg = store.registry_path
    reg.write_text(reg.read_text().replace('"row_count":', '"row_count":1', 1))
    with pytest.raises(ImmutableError, match="chain"):
        store.verify()


def test_licensed_rows_never_land_in_the_repository(tmp_path):
    with pytest.raises(LicenceError):
        DatasetStore(REPO_ROOT / "data" / "marketdata", allow_licensed=True)
    plain = DatasetStore(tmp_path / "plain")
    with pytest.raises(LicenceError):
        norgate(FX.synthetic_norgate_export(XA, date(2019, 12, 31)), plain)
    assert not (tmp_path / "plain").exists()
    ingest_fixture(fx_rows(date(2019, 1, 1), date(2019, 1, 31)), plain)   # synthetic is fine anywhere


# ================================================================ validation

def test_duplicates_exact_and_conflicting():
    assert codes([obs(), obs()]) == {"duplicate_exact": 1}
    assert "duplicate_conflict" in codes([obs(), obs(value=51.0)])
    # the same key in two publications is a revision, not a conflict
    a = obs(source_id="synthetic_receipt", published_at_utc="2019-02-01T20:00:00Z", settlement_status="preliminary")
    b = obs(source_id="synthetic_receipt", published_at_utc="2019-02-02T06:00:00Z", settlement_status="final",
            value=51.0)
    assert "duplicate_conflict" not in codes([a, b], src=FX.SYNTHETIC_RECEIPT)


def test_missing_sessions_and_missing_fraction():
    days = [date(2019, 2, d) for d in (4, 5, 6, 7, 8, 11, 12, 13, 14, 15)]
    rows = [obs(session_date=d, value=50 + i) for i, d in enumerate(days) if d != date(2019, 2, 7)]
    c = codes(rows, rules=Rules(max_missing_fraction=0.2))
    assert c == {"missing_session": 1}
    c = codes(rows, rules=Rules(max_missing_fraction=0.05))
    assert c["missing_fraction"] == 1
    holiday_cal = {"SYN_XA": set(days) - {date(2019, 2, 7)}}                 # an exchange holiday is not a gap
    assert codes(rows, rules=Rules(calendars=holiday_cal)) == {}


def test_stale_runs():
    days = [date(2019, 2, d) for d in (4, 5, 6, 7, 8, 11, 12)]
    rows = [obs(session_date=d, value=50.0 if i < 6 else 51.0) for i, d in enumerate(days)]
    assert codes(rows) == {"stale_run": 1}
    assert codes(rows, rules=Rules(stale_run=7)) == {}


@pytest.mark.parametrize("kw, code", [
    (dict(source_id="synthetic_receipt", published_at_utc="2019-02-01T12:00:00Z"), "published_before_observed"),
    (dict(source_id="synthetic_receipt", published_at_utc="2026-11-20T00:00:00Z"),
     "lookahead_published_after_retrieval"),
    (dict(source_id="synthetic_receipt", published_at_utc="2019-02-02T00:00:00Z",
          first_seen_utc="2019-02-01T23:00:00Z"), "seen_before_published"),
    (dict(observed_at_utc="2019-02-02T19:30:00Z"), "observed_date_mismatch"),
    (dict(session_date=date(2019, 2, 2)), "non_session_date"),
    (dict(session_date=date(2019, 3, 18), contract_id="XA-2019H"), "after_last_trade"),
    (dict(session_date=date(2017, 11, 1), contract_id="XA-2019H"), "before_first_trade"),
    (dict(session_date=date(2026, 11, 19), contract_id="XA-2026Z"), "lookahead_future_session"),
    (dict(first_seen_utc="2026-11-19T00:00:01Z"), "lookahead_seen_after_retrieval"),
    (dict(adjustment="back_adjusted"), "adjusted_price_stored"),
    (dict(instrument_id="SYN_NONE"), "unknown_instrument"),
    (dict(contract_id="XA-2031H"), "unknown_contract"),
    (dict(contract_id=None), "future_without_contract"),
    (dict(contract_id="XB-2019H"), "contract_root_mismatch"),
    (dict(instrument_id="SYN_FXAB", field="mid"), "contract_on_non_future"),
    (dict(field="volume", value=-1.0), "negative_count"),
])
def test_timestamp_reference_and_lookahead_errors(kw, code):
    contracts = dict(XA, **FX.synthetic_contracts("XA", "SYN_XA", 2026, 2026),
                     **FX.synthetic_contracts("XB", "SYN_XB", 2019, 2019))
    src = FX.SYNTHETIC_RECEIPT if kw.get("source_id") == "synthetic_receipt" else FX.SYNTHETIC_EOD
    _, rep = validate([obs(**kw)], INST, contracts, src, RETRIEVED, Rules())
    assert code in rep.codes("error"), rep.codes()


def test_prices_ohlc_and_signs():
    d = date(2019, 2, 1)
    bar = [obs(field="open", value=50), obs(field="high", value=49), obs(field="low", value=48),
           obs(field="settle", value=48.5)]
    assert codes(bar)["ohlc_inconsistent"] == 1
    assert codes([obs(value=-3.0)]) == {"nonpositive_price": 1}                     # futures: a warning
    _, rep = validate([obs(value=-3.0)], INST, XA, FX.SYNTHETIC_EOD, RETRIEVED)
    assert rep.ok
    fx = Observation("SYN_FXAB", d, "mid", 0.0, "synthetic_eod", RETRIEVED)
    _, rep = validate([fx], INST, {}, FX.SYNTHETIC_EOD, RETRIEVED)
    assert not rep.ok                                                               # currencies: an error


def test_validation_errors_stop_ingestion_and_store_nothing(store):
    rows = fx_rows(date(2019, 1, 1), date(2019, 1, 31))
    rows.append(dict(rows[3], value="9.99"))                                         # conflicting duplicate
    with pytest.raises(ValidationFailed) as e:
        ingest_fixture(rows, store)
    assert "duplicate_conflict" in e.value.report.codes("error")
    assert not (store.root / "datasets").exists() and store.registry() == []


def test_validation_reports_carry_no_values(store):
    files = FX.synthetic_norgate_export(XA, date(2019, 12, 31), drop={("XA-2019H", date(2019, 2, 7))})
    r = norgate(files, store)
    assert r.report["warnings"] == {"missing_session": 1}                  # the settle gap (o/h/l are not counted)
    text = json.dumps(store.load(r.dataset_id)["validation"])
    settle = FX.synthetic_price(0, "XA", "XA-2019H", date(2019, 2, 6))
    assert f"{settle:.2f}" not in text and "value" not in text.replace("values", "")


# ================================================================ adapters

def test_norgate_adapter_checks_the_manifest_before_reading(store):
    files = FX.synthetic_norgate_export(XA, date(2019, 12, 31))
    bad = dict(files)
    k = next(f for f in files if f.startswith("contracts/"))
    bad[k] = files[k].replace(b"\r\n", b"\n")                                  # a line-ending conversion
    with pytest.raises(ProvenanceError, match="manifest hash"):
        norgate(bad, store)
    extra = dict(files, **{"contracts/XA/XA-2030H.csv": files[k]})
    with pytest.raises(ProvenanceError, match="not in manifest"):
        norgate(extra, store)
    with pytest.raises(ProvenanceError, match="generated_utc"):
        norgate(files, store, retrieved=datetime(2019, 12, 31, tzinfo=UTC))
    with pytest.raises(SchemaError, match="never guessed"):
        ingest(NorgateExportAdapter({"XB": "SYN_XB"}, INST, NG_SRC), files, request={}, retrieved_utc=RETRIEVED,
               instruments=INST, store=store, fence=FENCE, caller="session", policy="exclude")
    with pytest.raises(SchemaError):
        NorgateExportAdapter({"XA": "SYN_FXAB"}, INST)


def test_norgate_close_is_stored_as_unadjusted_final_settlement(store):
    files = FX.synthetic_norgate_export(XA, date(2019, 12, 31))
    r = norgate(files, store)
    rows = store.load(r.dataset_id)["observations"]
    s = [o for o in rows if o.contract_id == "XA-2019H" and o.session_date == date(2019, 2, 6) and o.field == "settle"]
    assert len(s) == 1 and s[0].value == FX.synthetic_price(0, "XA", "XA-2019H", date(2019, 2, 6))
    assert s[0].settlement_status == "final" and s[0].adjustment == "none"
    assert {o.field for o in rows} == {"open", "high", "low", "settle", "volume", "open_interest"}
    ref = store.load(r.dataset_id)["reference"]
    c = next(c for c in ref["contracts"] if c["contract_id"] == "XA-2019H")
    assert c["last_trade"] == "2019-03-15" and c["first_notice"] == "2019-03-08"


def test_databento_adapter_maps_statistics_and_refuses_unknown_symbols(store):
    raw, sm = FX.synthetic_databento_statistics(XA, INST["SYN_XA"], date(2019, 1, 2), date(2019, 1, 31))
    req = dict(DB_REQ, symbol_map=sm)
    r = ingest(DatabentoStatisticsAdapter(INST), {"stats.csv": raw}, request=req, retrieved_utc=RETRIEVED,
               instruments=INST, contracts=XA, store=store, fence=FENCE, caller="session")
    rows = store.load(r.dataset_id)["observations"]
    assert {o.settlement_status for o in rows if o.field == "settle"} == {"preliminary", "final"}
    assert all(o.published_at_utc is not None for o in rows)
    with pytest.raises(SchemaError, match="symbol map"):
        ingest(DatabentoStatisticsAdapter(INST), {"stats.csv": raw}, request=dict(DB_REQ, symbol_map={"ZZZ": "XA-2019H"}),
               retrieved_utc=RETRIEVED, instruments=INST, contracts=XA, store=store, fence=FENCE, caller="session")
    plan = plan_request(["XA-2019H", "XA-2019M"], date(2019, 1, 2), date(2019, 1, 31))
    assert plan["symbol_map"] == {"XAH19": "XA-2019H", "XAM19": "XA-2019M"} and plan["schema"] == "statistics"


# ================================================================ the fence

def test_default_fence_refuses_post_2019_rows(store):
    files = FX.synthetic_norgate_export(XA, date(2020, 3, 31))
    with pytest.raises(FenceRefused, match="embargo"):
        norgate(files, store, policy="refuse")
    assert store.registry() == []


def test_excluded_rows_are_never_parsed_and_raw_files_not_copied(store):
    rows = fx_rows(date(2019, 12, 2), date(2019, 12, 31))
    rows += [{"instrument_id": "SYN_FXAB", "session_date": "2020-01-02", "field": "mid", "value": "NOT A NUMBER"}]
    with pytest.raises(FenceRefused):
        ingest_fixture(rows, store)
    r = ingest_fixture(rows, store, policy="exclude")                       # the garbage value was never read
    assert r.manifest.fence["excluded"] == {"embargo": {"rows": 1, "first_session": "2020-01-02",
                                                        "last_session": "2020-01-02"}}
    assert r.manifest.coverage["last_session"] == "2019-12-31"
    assert not (store.root / "raw").exists()                                # raw holds protected dates: not copied
    clean = ingest_fixture(fx_rows(date(2019, 1, 1), date(2019, 1, 31)), store)
    assert any((store.root / "raw").iterdir()) and clean.manifest.fence["excluded"] == {}


def reserve_fence():
    return roles.Fence(date(2015, 12, 31), {"fx_daily": (date(2017, 1, 2), date(2018, 12, 31))}, True)


def test_reserve_rows_need_the_runner_and_a_verified_designated_token(store):
    rows = fx_rows(date(2017, 3, 1), date(2017, 3, 31))
    fence = reserve_fence()
    with pytest.raises(FenceRefused, match="runner only"):
        ingest_fixture(rows, store, fence=fence, caller="session")
    with pytest.raises(FenceRefused, match="verified"):
        ingest_fixture(rows, store, fence=fence, caller="runner")
    unverified = roles.RunnerToken("AB-0001", "h", False, frozenset({("fx_daily", "W1")}))
    with pytest.raises(FenceRefused):
        ingest_fixture(rows, store, fence=fence, caller="runner", token=unverified, window_id="W1")
    token = roles.RunnerToken("AB-0001", "h", True, frozenset({("fx_daily", "W1")}))
    with pytest.raises(FenceRefused, match="designated"):
        ingest_fixture(rows, store, fence=fence, caller="runner", token=token, window_id="W2")
    r = ingest_fixture(rows, store, fence=fence, caller="runner", token=token, window_id="W1")
    assert r.manifest.fence["admitted"] == {"reserve": len(rows)}
    with pytest.raises(FenceRefused, match="runner only"):                  # a session cannot load it either
        VintageSet(store, [r.dataset_id], INST, {FX.SYNTHETIC_EOD.source_id: FX.SYNTHETIC_EOD}, CLOCK)
    vs = VintageSet(store, [r.dataset_id], INST, {FX.SYNTHETIC_EOD.source_id: FX.SYNTHETIC_EOD}, CLOCK,
                    caller="runner")
    assert vs.summary()["versions"] == len(rows)
    disabled = replace(fence, enabled=False)
    with pytest.raises(FenceRefused, match="embargo"):
        ingest_fixture(rows, store, fence=disabled, caller="runner", token=token, window_id="W1")


def test_forward_rows_after_a_freeze_are_runner_only(store):
    fence = roles.Fence(date(2019, 12, 31), {}, False)
    rows = fx_rows(date(2021, 2, 1), date(2021, 2, 26))
    with pytest.raises(FenceRefused, match="runner only"):
        ingest_fixture(rows, store, fence=fence, caller="session", freeze=date(2021, 1, 15))
    r = ingest_fixture(rows, store, fence=fence, caller="runner", freeze=date(2021, 1, 15))
    assert r.manifest.fence["admitted"] == {"forward": len(rows)}
    with pytest.raises(FenceRefused):                                         # no freeze: embargo for everyone
        ingest_fixture(rows, store, fence=fence, caller="runner")


def test_no_data_callers_cannot_ingest(store):
    for caller in ("generator_blind", "critic", "nobody"):
        with pytest.raises(FenceRefused):
            ingest_fixture(fx_rows(date(2019, 1, 1), date(2019, 1, 31)), store, caller=caller)


def test_the_engine_reader_still_applies_the_fence(store):
    r = ingest_fixture(fx_rows(date(2019, 1, 1), date(2019, 12, 31)), store)
    vs = VintageSet(store, [r.dataset_id], INST, {FX.SYNTHETIC_EOD.source_id: FX.SYNTHETIC_EOD}, CLOCK)
    rd = vs.reader(caller="session", domain="fx_daily", fence=FENCE)
    rd.window(date(2019, 1, 1), date(2019, 12, 31))
    with pytest.raises(roles.RoleError):
        rd.window(date(2019, 6, 1), date(2020, 1, 31))


# ================================================================ availability, revisions, look-ahead

def test_three_times_are_kept_apart():
    xa = INST["SYN_XA"]
    d = date(2019, 2, 1)                                         # close 13:30 Chicago = 19:30 UTC
    o = obs(session_date=d, first_seen_utc="2019-02-01T21:00:00Z")
    a = availability(o, xa, FX.SYNTHETIC_EOD)                    # delay 60 min: nominal 20:30, seen 21:00
    assert a.basis == FIRST_SEEN and a.observed_declared
    assert a.published_utc == datetime(2019, 2, 1, 20, 30, tzinfo=UTC)
    assert a.available_utc == datetime(2019, 2, 1, 21, 0, tzinfo=UTC)
    late = obs(session_date=d, first_seen_utc="2019-02-04T21:00:00Z")    # after nominal + 24h grace
    assert availability(late, xa, FX.SYNTHETIC_EOD, monitoring_start=datetime(2019, 1, 1, tzinfo=UTC)).basis == LATE
    back = availability(late, xa, FX.SYNTHETIC_EOD)                       # before monitoring began: backfill
    assert back.basis == BACKFILL and back.reconstructed and back.available_utc == a.published_utc
    rec = obs(session_date=d, source_id="synthetic_receipt", published_at_utc="2019-02-02T06:30:00Z")
    v = availability(rec, xa, FX.SYNTHETIC_RECEIPT)
    assert v.basis == VENDOR and not v.reconstructed and v.available_utc.hour == 6
    with pytest.raises(MarketDataError):
        availability(obs(session_date=d), xa, norgate_source())           # no declared delay: no availability


def test_research_clock_maps_times_to_decision_days():
    assert CLOCK.available_day(datetime(2019, 2, 1, 21, 59, tzinfo=UTC)) == date(2019, 2, 1)   # 16:59 New York
    assert CLOCK.available_day(datetime(2019, 2, 1, 22, 0, tzinfo=UTC)) == date(2019, 2, 1)    # 17:00 exactly
    assert CLOCK.available_day(datetime(2019, 2, 1, 22, 1, tzinfo=UTC)) == date(2019, 2, 2)
    assert CLOCK.available_day(datetime(2019, 7, 1, 21, 1, tzinfo=UTC)) == date(2019, 7, 2)    # summer time


def test_preliminary_then_final_settlement_is_a_timed_revision(store):
    d = date(2019, 2, 1)
    raw, sm = FX.synthetic_databento_statistics(XA, INST["SYN_XA"], date(2019, 1, 2), date(2019, 2, 28),
                                                revise_final={("XA-2019H", d): 99.99})
    r = ingest(DatabentoStatisticsAdapter(INST), {"s.csv": raw}, request=dict(DB_REQ, symbol_map=sm),
               retrieved_utc=RETRIEVED, instruments=INST, contracts=XA, store=store, fence=FENCE, caller="session")
    vs = VintageSet(store, [r.dataset_id], INST, {DB_SRC.source_id: DB_SRC}, CLOCK)
    name = series_name(DB_SRC.source_id, "SYN_XA", "XA-2019H", "settle")
    prelim = FX.synthetic_price(0, "XA", "XA-2019H", d)
    assert vs.as_of(name, datetime(2019, 2, 1, 19, 29, tzinfo=UTC)).get(d) is None    # before the close
    assert vs.as_of(name, datetime(2019, 2, 1, 21, 0, tzinfo=UTC))[d] == prelim
    assert vs.as_of(name, datetime(2019, 2, 2, 6, 31, tzinfo=UTC))[d] == 99.99         # final at close + 11 h
    assert vs.summary()["revisions"] == 1 and not vs.reconstructed()
    w = vs.reader(caller="session", domain="futures_daily", fence=FENCE).window(date(2019, 1, 2), date(2019, 2, 28))
    assert w.as_of(name, d)[1][-1] == prelim and w.as_of(name, date(2019, 2, 2))[1][-1] == 99.99


def test_snapshot_revisions_are_available_only_when_seen(store):
    d = date(2019, 2, 6)
    t1, t2 = datetime(2019, 2, 7, 3, tzinfo=UTC), datetime(2019, 3, 1, 3, tzinfo=UTC)
    contracts = {k: v for k, v in XA.items() if k == "XA-2019H"}
    s1 = FX.synthetic_norgate_export(contracts, date(2019, 2, 6), generated_utc=t1)
    s2 = FX.synthetic_norgate_export(contracts, date(2019, 2, 28), generated_utc=t2, revise={("XA-2019H", d): 77.77})
    r1, r2 = norgate(s1, store, retrieved=t1), norgate(s2, store, retrieved=t2)
    vs = VintageSet(store, [r2.dataset_id, r1.dataset_id], INST, {NG_SRC.source_id: NG_SRC}, CLOCK)
    name = series_name(NG_SRC.source_id, "SYN_XA", "XA-2019H", "settle")
    orig = FX.synthetic_price(0, "XA", "XA-2019H", d)
    assert vs.as_of(name, t2 - timedelta(seconds=1))[d] == orig        # the revision is not backdated
    assert vs.as_of(name, t2)[d] == 77.77
    assert vs.revisions[name] == 1                                      # overlapping equal rows are re-deliveries
    assert vs.summary()["revisions"] == 4                               # the revised bar: open, high, low, settle
    assert vs.reconstructed()                                           # history before monitoring: backfill
    with pytest.raises(PitError, match="reconstructed"):
        vs.pit_store().require_historical_evidence()


def test_a_gap_filled_by_a_later_snapshot_is_late_not_backfilled(store):
    """Snapshot 1 covers 7 Feb but lacks it; snapshot 2 (three weeks later) delivers it. The value was not
    knowable before snapshot 2, so it must not be backdated to its nominal publication."""
    gap = date(2019, 2, 7)
    contracts = {k: v for k, v in XA.items() if k == "XA-2019H"}
    t1, t2 = datetime(2019, 2, 8, 3, tzinfo=UTC), datetime(2019, 3, 1, 3, tzinfo=UTC)
    s1 = FX.synthetic_norgate_export(contracts, date(2019, 2, 7), generated_utc=t1, drop={("XA-2019H", gap)})
    s2 = FX.synthetic_norgate_export(contracts, date(2019, 2, 28), generated_utc=t2)
    ids = [norgate(s1, store, retrieved=t1).dataset_id, norgate(s2, store, retrieved=t2).dataset_id]
    vs = VintageSet(store, ids, INST, {NG_SRC.source_id: NG_SRC}, CLOCK)
    name = series_name(NG_SRC.source_id, "SYN_XA", "XA-2019H", "settle")
    assert gap not in vs.as_of(name, t2 - timedelta(seconds=1))
    assert gap in vs.as_of(name, t2)
    assert vs.versions[(name, gap)][0].basis == LATE
    assert vs.versions[(name, date(2019, 2, 6))][0].basis == BACKFILL


def test_rows_must_match_their_source_timestamp_semantics():
    assert "missing_publication_time" in codes([obs(source_id="synthetic_receipt")], src=FX.SYNTHETIC_RECEIPT)
    assert "unexpected_publication_time" in codes([obs(published_at_utc="2019-02-02T06:00:00Z")])
    assert "source_mismatch" in codes([obs(source_id="other")])


def test_pit_store_never_returns_a_value_before_its_availability_day(store):
    """Daily live captures (first seen before nominal publication): a session's settlement is published at the
    close + 600 minutes (04:30 UTC next day) and so first usable at the next day's decision time."""
    contracts = {k: v for k, v in XA.items() if k == "XA-2019U"}
    t1, t2 = datetime(2019, 6, 3, 23, tzinfo=UTC), datetime(2019, 6, 4, 23, tzinfo=UTC)
    r1 = norgate(FX.synthetic_norgate_export(contracts, date(2019, 6, 3), generated_utc=t1), store, retrieved=t1)
    r2 = norgate(FX.synthetic_norgate_export(contracts, date(2019, 6, 4), generated_utc=t2), store, retrieved=t2)
    vs = VintageSet(store, [r1.dataset_id, r2.dataset_id], INST, {NG_SRC.source_id: NG_SRC}, CLOCK)
    assert vs.summary()["basis"]["first_seen"] == 12                  # the 3 and 4 June bars; the rest backfill
    name = series_name(NG_SRC.source_id, "SYN_XA", "XA-2019U", "settle")
    w = vs.reader(caller="session", domain="futures_daily", fence=FENCE).window(date(2019, 1, 2), date(2019, 6, 28))
    p, _, a = w.as_of_with_availability(name, date(2019, 6, 5))
    avail = {pp.astype(object): aa.astype(object) for pp, aa in zip(p, a)}
    assert avail[date(2019, 6, 3)] == date(2019, 6, 4) and avail[date(2019, 6, 4)] == date(2019, 6, 5)
    assert w.as_of(name, date(2019, 6, 4))[0][-1].astype(object) == date(2019, 6, 3)
    assert w.as_of(name, date(2019, 6, 3))[0][-1].astype(object) == date(2019, 5, 31)
    assert all(aa >= pp for pp, aa in zip(p, a))


def _continuous(store, files_list, t, *, method="difference", adjustments=()):
    ids = [norgate(f, store, retrieved=ret).dataset_id for f, ret in files_list]
    vs = VintageSet(store, ids, INST, {NG_SRC.source_id: NG_SRC}, CLOCK)
    w = vs.reader(caller="session", domain="futures_daily", fence=FENCE).window(date(2018, 1, 2), date(2019, 12, 31))
    dec = vs.decision_time(t)
    return CT.build(w, NG_SRC.source_id, "SYN_XA", list(XA.values()), t, method=method, adjustments=adjustments,
                    decision_time=dec)


def test_continuous_series_as_of_t_ignores_everything_after_t(tmp_path):
    t = date(2019, 5, 31)
    base = FX.synthetic_norgate_export(XA, date(2019, 12, 31))
    a = _continuous(DatasetStore(tmp_path / "a", allow_licensed=True), [(base, RETRIEVED)], t)
    # different future: later sessions perturbed, plus a later snapshot revising pre-t values (seen after t)
    later = {("XA-2019U", d): 10.0 for d in (date(2019, 6, 3), date(2019, 6, 4), date(2019, 9, 3))}
    perturbed = FX.synthetic_norgate_export(XA, date(2019, 12, 31), revise=later)
    rev = FX.synthetic_norgate_export(XA, date(2019, 12, 31), revise={("XA-2019M", date(2019, 3, 8)): 1.0},
                                      generated_utc=RETRIEVED + timedelta(days=1))
    b = _continuous(DatasetStore(tmp_path / "b", allow_licensed=True),
                    [(perturbed, RETRIEVED), (rev, RETRIEVED + timedelta(days=1))], t)
    assert a[0] == b[0] and a[2] == b[2] and (a[1] == b[1]).all()
    assert a[0][-1] <= t and len(set(a[2])) >= 4                     # several rolls, nothing after t


def test_continuous_back_adjustment_changes_only_with_rolls_known_at_t(store):
    files = FX.synthetic_norgate_export(XA, date(2019, 12, 31))
    early, _, held_e = _continuous(store, [(files, RETRIEVED)], date(2019, 2, 28))
    late_days, late_vals, held_l = _continuous(store, [(files, RETRIEVED)], date(2019, 5, 31))
    raw_days, raw_vals, _ = _continuous(store, [(files, RETRIEVED)], date(2019, 5, 31), method="none")
    assert held_l[-1] != held_e[-1]                                   # a roll between the two decision days
    i = late_days.index(early[-1])
    assert late_vals[i] != raw_vals[i]                                # history re-based by the later roll ...
    _, early_vals, _ = _continuous(store, [(files, RETRIEVED)], date(2019, 2, 28))
    j = early.index(early[-1])
    assert early_vals[j] == raw_vals[raw_days.index(early[-1])]      # ... but not as of the earlier day


def test_adjustment_events_apply_only_once_announced(store):
    files = FX.synthetic_norgate_export(XA, date(2019, 12, 31))
    t = date(2019, 5, 31)
    ev = AdjustmentEvent("SYN_XA", "price_unit_change", date(2019, 4, 1), datetime(2019, 6, 10, tzinfo=UTC),
                         factor=100.0, reference="synthetic exchange notice")
    plain = _continuous(store, [(files, RETRIEVED)], t, method="none")
    with_unknown = _continuous(store, [(files, RETRIEVED)], t, method="none", adjustments=[ev])
    assert (plain[1] == with_unknown[1]).all()
    known = replace(ev, announced_utc=datetime(2019, 3, 1, tzinfo=UTC))
    adj = _continuous(store, [(files, RETRIEVED)], t, method="none", adjustments=[known])
    before = [k for k, d in enumerate(plain[0]) if d < date(2019, 4, 1)]
    assert adj[1][before[0]] == pytest.approx(plain[1][before[0]] * 100)


def test_missing_roll_price_is_an_error_not_a_fill(store):
    sched = CT.roll_schedule(list(XA.values()), date(2019, 1, 2), date(2019, 5, 31))
    last_old = next(d for (d, c), (_, c2) in zip(sched, sched[1:]) if c != c2)
    nxt = next(c2 for (d, c), (_, c2) in zip(sched, sched[1:]) if d == last_old)
    files = FX.synthetic_norgate_export(XA, date(2019, 12, 31), drop={(nxt, last_old)})
    with pytest.raises(MarketDataError, match="both prices"):
        _continuous(store, [(files, RETRIEVED)], date(2019, 5, 31))
    days, vals, held = _continuous(store, [(files, RETRIEVED)], date(2019, 5, 31), method="none")
    assert last_old in days and len(vals) == len(days)               # the held contract's own row is there


def test_missing_sessions_stay_missing_through_the_pit_layer(store):
    gap = date(2019, 2, 7)
    files = FX.synthetic_norgate_export(XA, date(2019, 12, 31), drop={("XA-2019H", gap)})
    r = norgate(files, store)
    vs = VintageSet(store, [r.dataset_id], INST, {NG_SRC.source_id: NG_SRC}, CLOCK)
    name = series_name(NG_SRC.source_id, "SYN_XA", "XA-2019H", "settle")
    w = vs.reader(caller="session", domain="futures_daily", fence=FENCE).window(date(2019, 1, 2), date(2019, 3, 15))
    p, _ = w.as_of(name, date(2019, 3, 15))
    assert gap not in {x.astype(object) for x in p} and date(2019, 2, 6) in {x.astype(object) for x in p}


def test_vintage_set_refuses_sources_without_availability(store):
    files = FX.synthetic_norgate_export(XA, date(2019, 12, 31))
    bare = norgate_source()
    r = norgate(files, store, src=bare)
    with pytest.raises(MarketDataError, match="availability cannot be computed"):
        VintageSet(store, [r.dataset_id], INST, {bare.source_id: bare}, CLOCK)
    with pytest.raises(MarketDataError, match="differs"):
        VintageSet(store, [r.dataset_id], INST, {bare.source_id: NG_SRC}, CLOCK)


def test_fixture_generators_are_order_free_and_asof_stable():
    a = FX.synthetic_norgate_export(XA, date(2019, 6, 28))
    b = FX.synthetic_norgate_export(XA, date(2019, 12, 31))
    k = "contracts/XA/XA-2019H.csv"
    assert a[k] == b[k]                                       # an expired contract does not depend on as-of
    assert FX.synthetic_price(0, "XA", "XA-2019H", date(2019, 2, 6)) == \
        FX.synthetic_price(0, "XA", "XA-2019H", date(2019, 2, 6))
    assert all(not f.startswith("/") for f in a)


# ================================================================ command line

def test_cli_demo_runs_end_to_end(tmp_path, capsys):
    from manhattan.marketdata.__main__ import main
    assert main(["demo", "--out", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["registry_records"] == 2 and out["vintages"]["revisions"] == 1
    assert out["norgate_fence"]["excluded"]["embargo"]["first_session"] == "2020-01-01"
    assert main(["verify", "--store", str(tmp_path / "store")]) == 0


def _write_snapshot(root, files):
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def _instruments_file(path):
    xa = INST["SYN_XA"].to_dict()
    path.write_text(json.dumps([dict(xa, norgate_market="XA")]))
    return path


from manhattan.testing import reads_hand_edited_file  # noqa: E402


@reads_hand_edited_file
def test_cli_ingest_norgate_uses_the_configured_fence(tmp_path, capsys):
    from manhattan.marketdata.__main__ import main
    snap = tmp_path / "2099-01_synthetic"
    _write_snapshot(snap, FX.synthetic_norgate_export(XA, date(2020, 3, 31)))
    args = ["ingest-norgate", "--snapshot", str(snap), "--instruments", str(_instruments_file(tmp_path / "i.json")),
            "--retrieved", "2026-11-19T00:00:00Z"]
    assert main(args + ["--store", str(tmp_path / "store")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["coverage"]["last_session"] <= "2019-12-31" and out["fence"]["excluded"]
    assert len(out["provenance_gaps"]) == 3                     # no delay declared: stored, not PIT-ready
    with pytest.raises(LicenceError):
        main(args + ["--store", str(REPO_ROOT / "tmp-marketdata-store")])
    assert not (REPO_ROOT / "tmp-marketdata-store").exists()
    assert main(args + ["--store", str(tmp_path / "store"), "--markets", "ZZ"]) == 2
